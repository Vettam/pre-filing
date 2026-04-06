from fastapi import APIRouter, Depends, Request
from app.schemas.requests import (
    IndexRowCreate, IndexRowUpdate, IndexReorder,
)
from app.utils import compute_expected_pages, compute_end_label
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound, BadRequest


indexRowsRouter = APIRouter()


def compute_page_numbers(sections: list, docs_by_section: dict) -> list:
    """
    Compute running page labels for Part 1 and Part 2 based on
    page_label_style and page_label_prefix of each section.
 
    Part 1 and Part 2 share a single running cursor per style.
    - 'both': same label appears in both part1 and part2 columns
    - 'part1': label appears only in part1 column
    - 'part2': label appears only in part2 column
 
    Styles:
      - numeric:       1, 2, 3 ...          (shared numeric counter)
      - alpha_only:    A, B, NS ...          (single label, no number, independent per prefix)
      - alpha_numeric: A1, A2, NS1, NS2 ... (prefix + shared counter per prefix)
      - roman:         i, ii, iii ...        (shared roman counter)
      - none:          always blank
    """
 
    # ── Running counters ─────────────────────────────────────────────────────
    numeric_counter = 1        # shared across all numeric sections
    roman_counter   = 1        # shared across all roman sections
    prefix_counters = {}       # per prefix counter for alpha_numeric e.g. {"A": 1, "NS": 1}
 
    def to_roman(n: int) -> str:
        vals = [
            (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
            (100,  "c"), (90,  "xc"), (50,  "l"), (40,  "xl"),
            (10,   "x"), (9,   "ix"), (5,   "v"), (4,   "iv"), (1, "i")
        ]
        result = ""
        for v, s in vals:
            while n >= v:
                result += s
                n -= v
        return result
 
    def make_label(style: str, prefix: str | None, page_count: int) -> tuple[str | None, str | None]:
        """
        Returns (start_label, end_label) for a section given its style and page count.
        end_label is None if it's the same as start_label (single page or alpha_only).
        Advances the appropriate counter.
        """
        nonlocal numeric_counter, roman_counter
 
        if style == "none" or style is None:
            return None, None
 
        if style == "numeric":
            start = numeric_counter
            end   = numeric_counter + page_count - 1
            numeric_counter += page_count
            return str(start), str(end) if end != start else None
 
        if style == "roman":
            start = roman_counter
            end   = roman_counter + page_count - 1
            roman_counter += page_count
            start_label = to_roman(start)
            end_label   = to_roman(end) if end != start else None
            return start_label, end_label
 
        if style == "alpha_only":
            # Entire section gets a single label equal to the prefix — no counter needed
            return prefix, None
 
        if style == "alpha_numeric":
            if prefix not in prefix_counters:
                prefix_counters[prefix] = 1
            start = prefix_counters[prefix]
            end   = prefix_counters[prefix] + page_count - 1
            prefix_counters[prefix] += page_count
            start_label = f"{prefix}{start}"
            end_label   = f"{prefix}{end}" if end != start else None
            return start_label, end_label
 
        return None, None
 
    # ── Build rows ────────────────────────────────────────────────────────────
    rows = []
 
    for order_idx, section in enumerate(sections):
        section_id = section["id"]
        col        = section.get("page_number_column") or "part1"
        style      = section.get("page_label_style") or "numeric"
        prefix     = section.get("page_label_prefix")
 
        # Sum page counts from documents in this section
        docs = docs_by_section.get(section_id, [])
        total_pages = None
        if docs:
            counts = [d.get("paper_book_files", {}).get("page_count") for d in docs]
            if any(c is not None for c in counts):
                total_pages = sum(c or 0 for c in counts)
 
        row = {
            "section_id":       section_id,
            "particulars":      section["name"],
            "order_index":      order_idx + 1,
            "sl_no":            str(order_idx + 1),
            "is_custom":        False,
            "is_edited":        False,
            "page_start_part1": None,
            "page_end_part1":   None,
            "page_start_part2": None,
            "page_end_part2":   None,
        }
 
        if total_pages is not None and total_pages > 0:
            start_label, end_label = make_label(style, prefix, total_pages)
 
            if col == "both":
                row["page_start_part1"] = start_label
                row["page_end_part1"]   = end_label
                row["page_start_part2"] = start_label
                row["page_end_part2"]   = end_label
 
            elif col == "part1":
                row["page_start_part1"] = start_label
                row["page_end_part1"]   = end_label
 
            elif col == "part2":
                row["page_start_part2"] = start_label
                row["page_end_part2"]   = end_label
        else:
            # Section has no docs or no page counts
            # Leave page numbers as None (blank in index)
            # Do NOT advance any counter
            pass
 
        rows.append(row)
 
    return rows


@indexRowsRouter.post("/generate/", dependencies=[Depends(AuthenticationRequired)])
async def generate_index(
    request: Request,
    paper_book_id: str,
):
    """
    Auto-generate index rows from sections and their documents.
    Deletes existing rows and regenerates.
    """
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")
 
    # Fetch sections ordered — includes page_label_style and page_label_prefix
    sections_res = (
        await supabase.table("paper_book_sections")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    sections = sections_res.data or []
 
    # Fetch all documents joined with page_count from paper_book_files
    docs_res = (
        await supabase.table("paper_book_documents")
        .select("*, paper_book_files(page_count)")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    docs = docs_res.data or []
 
    # Group docs by section
    docs_by_section: dict = {}
    for doc in docs:
        sid = doc.get("section_id")
        if sid:
            docs_by_section.setdefault(sid, []).append(doc)
 
    # Delete existing rows
    await supabase.table("paper_book_index_rows").delete().eq(
        "paper_book_id", paper_book_id
    ).execute()
 
    # Compute page labels
    rows = compute_page_numbers(sections, docs_by_section)
 
    if not rows:
        return Success(data={"index_rows": []}, message="No sections found")
 
    # Insert rows
    insert_payload = [{**row, "paper_book_id": paper_book_id} for row in rows]
    res = await supabase.table("paper_book_index_rows").insert(insert_payload).execute()
 
    # Update paper book status
    await supabase.table("paper_books").update({"status": "index_created"}).eq(
        "id", paper_book_id
    ).execute()
 
    response = {"index_rows": res.data}
    return Success(data=response, message="Index generated successfully")

@indexRowsRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def get_index(
    request: Request,
    paper_book_id: str,
):
    supabase = await get_supabase_client(request.state.token)
    dbResponse = (
        await supabase.table("paper_books")
        .select("*")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not dbResponse.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_index_rows")
        .select("*, paper_book_sections(id, paper_book_documents(id, paper_book_files(*)))")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    response = {"index_rows": res.data or [], "paperbook": dbResponse.data}
    return Success(data=response, message="Index rows fetched successfully")


@indexRowsRouter.post("/rows/", dependencies=[Depends(AuthenticationRequired)])
async def create_index_row(
    request: Request,
    paper_book_id: str,
    payload: IndexRowCreate,
):
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    # Determine shared order_index from whichever table has the higher max
    # so both section and index row are appended consistently
    if payload.order_index is not None:
        order_index = payload.order_index
    else:
        index_row_order_res = (
            await supabase.table("paper_book_index_rows")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        section_order_res = (
            await supabase.table("paper_book_sections")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        max_index_row_order = index_row_order_res.data[0]["order_index"] if index_row_order_res.data else 0
        max_section_order = section_order_res.data[0]["order_index"] if section_order_res.data else 0
        order_index = max(max_index_row_order, max_section_order) + 1

    # sl_no is always derived from order_index automatically
    sl_no = str(order_index)

    # If inserting in the middle, shift all existing rows with order_index >= new order_index
    # Fetch and update manually since supabase-py doesn't support column expressions in update
    rows_to_shift_res = (
        await supabase.table("paper_book_index_rows")
        .select("id, order_index")
        .eq("paper_book_id", paper_book_id)
        .gte("order_index", order_index)
        .execute()
    )
    for row in (rows_to_shift_res.data or []):
        await supabase.table("paper_book_index_rows").update(
            {"order_index": row["order_index"] + 1, "sl_no": str(row["order_index"] + 1)}
        ).eq("id", row["id"]).execute()

    # Also shift sections with order_index >= new order_index
    sections_to_shift_res = (
        await supabase.table("paper_book_sections")
        .select("id, order_index")
        .eq("paper_book_id", paper_book_id)
        .gte("order_index", order_index)
        .execute()
    )
    for section in (sections_to_shift_res.data or []):
        await supabase.table("paper_book_sections").update(
            {"order_index": section["order_index"] + 1}
        ).eq("id", section["id"]).execute()

    # Auto-create section with same name as particulars and same order_index
    section_res = (
        await supabase.table("paper_book_sections")
        .insert({
            "paper_book_id": paper_book_id,
            "name": payload.particulars,
            "order_index": order_index,
            "page_number_column": "both",
            "is_default": False,
        })
        .execute()
    )
    new_section = section_res.data[0]

    # Insert index row with same order_index and auto sl_no
    insert_data = {
        "paper_book_id": paper_book_id,
        "section_id": new_section["id"],
        "sl_no": sl_no,
        "particulars": payload.particulars,
        "page_start_part1": payload.page_start_part1,
        "page_end_part1": payload.page_end_part1,
        "page_start_part2": payload.page_start_part2,
        "page_end_part2": payload.page_end_part2,
        "remarks": payload.remarks,
        "order_index": order_index,
        "is_custom": True,
        "is_edited": False,
    }

    res = await supabase.table("paper_book_index_rows").insert(insert_data).execute()

    response = {
        "index_row": res.data,
        "section": new_section,
    }
    return Success(data=response, message="Index row created successfully")


@indexRowsRouter.patch("/rows/{row_id}/", dependencies=[Depends(AuthenticationRequired)])
async def update_index_row(
    request: Request,
    paper_book_id: str,
    row_id: str,
    payload: IndexRowUpdate,
):
    supabase = await get_supabase_client(request.state.token)
 
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")
 
    res = (
        await supabase.table("paper_book_index_rows")
        .select("*")
        .eq("id", row_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Index row not found")
 
    existing_row = res.data
    update_data  = payload.model_dump(exclude_none=True)
    update_data["is_edited"] = True
 
    # ── Page count mismatch validation ───────────────────────────────────────
    page_fields = {
        "page_start_part1", "page_end_part1",
        "page_start_part2", "page_end_part2",
    }
    page_fields_changed = any(f in update_data for f in page_fields)
 
    if page_fields_changed and existing_row.get("section_id"):
        # Fetch section to get page_label_style
        section_res = (
            await supabase.table("paper_book_sections")
            .select("page_label_style, page_number_column")
            .eq("id", existing_row["section_id"])
            .single()
            .execute()
        )
        section       = section_res.data or {}
        style         = section.get("page_label_style") or "numeric"
        page_col      = section.get("page_number_column") or "part1"
 
        # Fetch actual page count from documents in this section
        docs_res = (
            await supabase.table("paper_book_documents")
            .select("paper_book_files(page_count)")
            .eq("paper_book_id", paper_book_id)
            .eq("section_id", existing_row["section_id"])
            .execute()
        )
        actual_pages = 0
        for doc in (docs_res.data or []):
            files = doc.get("paper_book_files")
            pc = None
            if isinstance(files, dict):
                pc = files.get("page_count")
            elif isinstance(files, list) and files:
                pc = files[0].get("page_count")
            actual_pages += (pc or 0)
 
        # Determine which labels to validate against based on page_number_column
        # Use updated values from payload, fallback to existing row values
        if page_col in ("part1", "both"):
            start_label = update_data.get("page_start_part1") or existing_row.get("page_start_part1")
            end_label   = update_data.get("page_end_part1")   or existing_row.get("page_end_part1")
        else:
            start_label = update_data.get("page_start_part2") or existing_row.get("page_start_part2")
            end_label   = update_data.get("page_end_part2")   or existing_row.get("page_end_part2")
 
        expected_pages = compute_expected_pages(start_label, end_label, style)
 
        if expected_pages is not None and actual_pages > 0:
            update_data["has_page_count_mismatch"] = (expected_pages != actual_pages)
        else:
            # Can't validate (no docs yet, or style skipped) — clear any existing flag
            update_data["has_page_count_mismatch"] = False
 
    # ── Persist update ────────────────────────────────────────────────────────
    res = (
        await supabase.table("paper_book_index_rows")
        .update(update_data)
        .eq("id", row_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
 
    response = {"index_row": res.data}
    return Success(data=response, message="Index row updated successfully")


@indexRowsRouter.delete("/rows/{row_id}/", dependencies=[Depends(AuthenticationRequired)])
async def delete_index_row(
    request: Request,
    paper_book_id: str,
    row_id: str,
):
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_index_rows")
        .select("*")
        .eq("id", row_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Index row not found")

    await supabase.table("paper_book_sections").delete().eq("id", res.data["section_id"]).execute()

    response = {}
    return Success(data=response, message="Index row deleted successfully")


@indexRowsRouter.post("/rows/{row_id}/recalculate/", dependencies=[Depends(AuthenticationRequired)])
async def recalculate_index_row(
    request: Request,
    paper_book_id: str,
    row_id: str,
):
    """
    Fix the page_end of an index row to match the actual page count of its section.
    Keeps page_start unchanged. Recomputes page_end in the same label style.
    Clears has_page_count_mismatch flag after fix.
    """
    supabase = await get_supabase_client(request.state.token)
 
    # Verify paper book ownership
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")
 
    # Fetch index row
    res = (
        await supabase.table("paper_book_index_rows")
        .select("*")
        .eq("id", row_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Index row not found")
 
    row = res.data
 
    if not row.get("section_id"):
        raise BadRequest(
            error_code="no_linked_section",
            message="This index row has no linked section. Cannot recalculate."
        )
 
    # Fetch section for style and page_number_column
    section_res = (
        await supabase.table("paper_book_sections")
        .select("page_label_style, page_number_column")
        .eq("id", row["section_id"])
        .single()
        .execute()
    )
    if not section_res.data:
        raise NotFound(message="Linked section not found")
 
    section  = section_res.data
    style    = section.get("page_label_style") or "numeric"
    page_col = section.get("page_number_column") or "part1"
 
    # Skip recalculation for styles that don't support it
    if style in ("alpha_only", "none"):
        return Success(
            data={"index_row": row},
            message="Recalculation not applicable for this page label style"
        )
 
    # Fetch actual page count from documents in this section
    docs_res = (
        await supabase.table("paper_book_documents")
        .select("paper_book_files(page_count)")
        .eq("paper_book_id", paper_book_id)
        .eq("section_id", row["section_id"])
        .execute()
    )
    actual_pages = 0
    for doc in (docs_res.data or []):
        files = doc.get("paper_book_files")
        pc = None
        if isinstance(files, dict):
            pc = files.get("page_count")
        elif isinstance(files, list) and files:
            pc = files[0].get("page_count")
        actual_pages += (pc or 0)
 
    if actual_pages == 0:
        raise BadRequest(
            error_code="no_documents_with_page_counts",
            message="No documents with page counts found in this section. Cannot recalculate."
        )
 
    # Compute new end labels based on page_number_column
    update_data = {
        "is_edited":              True,
        "has_page_count_mismatch": False,
    }
 
    if page_col in ("part1", "both"):
        start_label = row.get("page_start_part1")
        new_end     = compute_end_label(start_label, actual_pages, style)
        if new_end is None:
            raise BadRequest(
                error_code="invalid_end_label",
                message=f"Cannot compute end label from start '{start_label}' with style '{style}'"
            )
        update_data["page_end_part1"] = new_end
        if page_col == "both":
            update_data["page_end_part2"] = new_end
 
    elif page_col == "part2":
        start_label = row.get("page_start_part2")
        new_end     = compute_end_label(start_label, actual_pages, style)
        if new_end is None:
            raise BadRequest(
                error_code="invalid_end_label",
                message=f"Cannot compute end label from start '{start_label}' with style '{style}'"
            )
        update_data["page_end_part2"] = new_end
 
    # Persist
    res = (
        await supabase.table("paper_book_index_rows")
        .update(update_data)
        .eq("id", row_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
 
    response = {"index_row": res.data}
    return Success(data=response, message="Index row recalculated successfully")


@indexRowsRouter.patch("/reorder/", dependencies=[Depends(AuthenticationRequired)])
async def reorder_index(
    request: Request,
    paper_book_id: str,
    payload: IndexReorder,
):
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    # Fetch ALL existing index rows
    all_rows_res = (
        await supabase.table("paper_book_index_rows")
        .select("id, order_index, sl_no, section_id")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    all_rows    = all_rows_res.data or []
    all_row_ids = {row["id"] for row in all_rows}

    # Build final order — payload first, remaining rows appended at end
    ordered_ids   = list(payload.ordered_ids)
    remaining_ids = [
        row["id"] for row in all_rows
        if row["id"] not in set(ordered_ids)
    ]
    final_order = ordered_ids + remaining_ids

    # Build row_id -> section_id map
    row_section_map = {row["id"]: row["section_id"] for row in all_rows}

    updated           = []
    section_new_order = {}  # section_id -> new order_index (first occurrence wins)

    for idx, row_id in enumerate(final_order):
        if row_id not in all_row_ids:
            continue

        new_order_index = idx + 1

        # Update index row order_index and sl_no
        res = (
            await supabase.table("paper_book_index_rows")
            .update({
                "order_index": new_order_index,
                "sl_no":       str(new_order_index),
            })
            .eq("id", row_id)
            .eq("paper_book_id", paper_book_id)
            .execute()
        )
        if res.data:
            updated.append(res.data[0])

        # Collect section order — first occurrence wins
        section_id = row_section_map.get(row_id)
        if section_id and section_id not in section_new_order:
            section_new_order[section_id] = new_order_index

    # Sync section order_index to match index row order
    for section_id, new_order_index in section_new_order.items():
        await supabase.table("paper_book_sections").update(
            {"order_index": new_order_index}
        ).eq("id", section_id).eq("paper_book_id", paper_book_id).execute()

    updated.sort(key=lambda r: r["order_index"])

    response = {"index_rows": updated}
    return Success(data=response, message="Index rows reordered successfully")
