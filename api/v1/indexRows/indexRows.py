from fastapi import APIRouter, Depends, Request
from app.schemas.requests import (
    IndexRowCreate, IndexRowUpdate, IndexReorder,
)
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound


indexRowsRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_INDEX_ROW = {
    "id": "ir-001",
    "paper_book_id": "pb-001",
    "section_id": "sec-001",
    "sl_no": "1",
    "particulars": "0/R on Limitation",
    "page_start_part1": 1,
    "page_end_part1": 2,
    "page_start_part2": None,
    "page_end_part2": None,
    "remarks": None,
    "order_index": 1,
    "is_custom": False,
    "is_edited": False,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

MOCK_INDEX_ROWS_LIST = [
    {
        "id": "ir-001",
        "paper_book_id": "pb-001",
        "section_id": "sec-001",
        "sl_no": "1",
        "particulars": "0/R on Limitation",
        "page_start_part1": 1,
        "page_end_part1": 2,
        "page_start_part2": None,
        "page_end_part2": None,
        "remarks": None,
        "order_index": 1,
        "is_custom": False,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "ir-002",
        "paper_book_id": "pb-001",
        "section_id": "sec-002",
        "sl_no": "2",
        "particulars": "Listing Performa",
        "page_start_part1": 3,
        "page_end_part1": 4,
        "page_start_part2": None,
        "page_end_part2": None,
        "remarks": None,
        "order_index": 2,
        "is_custom": False,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "ir-003",
        "paper_book_id": "pb-001",
        "section_id": "sec-003",
        "sl_no": "3",
        "particulars": "Cover page of the paper book",
        "page_start_part1": None,
        "page_end_part1": None,
        "page_start_part2": 1,
        "page_end_part2": 3,
        "remarks": None,
        "order_index": 3,
        "is_custom": False,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "ir-004",
        "paper_book_id": "pb-001",
        "section_id": "sec-004",
        "sl_no": "4",
        "particulars": "Note sheet",
        "page_start_part1": None,
        "page_end_part1": None,
        "page_start_part2": 4,
        "page_end_part2": 6,
        "remarks": None,
        "order_index": 4,
        "is_custom": False,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "ir-005",
        "paper_book_id": "pb-001",
        "section_id": "sec-005",
        "sl_no": "5",
        "particulars": "SLP with affidavit",
        "page_start_part1": 5,
        "page_end_part1": 10,
        "page_start_part2": 7,
        "page_end_part2": 12,
        "remarks": None,
        "order_index": 5,
        "is_custom": False,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "ir-006",
        "paper_book_id": "pb-001",
        "section_id": None,
        "sl_no": "6",
        "particulars": "Custom Row Added by User",
        "page_start_part1": 11,
        "page_end_part1": 12,
        "page_start_part2": None,
        "page_end_part2": None,
        "remarks": "Some remark",
        "order_index": 6,
        "is_custom": True,
        "is_edited": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

# ---------------------------------------------------------------------------


def compute_page_numbers(sections: list, docs_by_section: dict) -> list:
    """
    Compute running page numbers for Part 1 and Part 2.
    - Part 1 counter: increments for sections with page_number_column in (part1, both)
    - Part 2 counter: increments for sections with page_number_column in (part2, both)
    Page count comes from the documents' actual page counts (sum per section).
    If no documents in a section, page numbers are left None.
    """
    rows = []
    part1_cursor = 1
    part2_cursor = 1

    for order_idx, section in enumerate(sections):
        section_id = section["id"]
        col = section["page_number_column"]  # part1 | part2 | both

        docs = docs_by_section.get(section_id, [])
        # Sum page counts (None page_count treated as 0, so pages remain None)
        total_pages = None
        if docs:
            counts = [d.get("page_count") for d in docs]
            if any(c is not None for c in counts):
                total_pages = sum(c or 0 for c in counts)

        row = {
            "section_id": section_id,
            "particulars": section["name"],
            "order_index": order_idx + 1,
            "sl_no": str(order_idx + 1),
            "is_custom": False,
            "is_edited": False,
            "page_start_part1": None,
            "page_end_part1": None,
            "page_start_part2": None,
            "page_end_part2": None,
        }

        if total_pages is not None and total_pages > 0:
            if col in ("part1", "both"):
                row["page_start_part1"] = part1_cursor
                row["page_end_part1"] = part1_cursor + total_pages - 1
                part1_cursor += total_pages

            if col in ("part2", "both"):
                row["page_start_part2"] = part2_cursor
                row["page_end_part2"] = part2_cursor + total_pages - 1
                part2_cursor += total_pages
        else:
            # Section has no docs or no page counts: advance cursor only if col matches
            # Leave page numbers as None (blank in index)
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
    Deletes existing non-custom rows and regenerates.
    Custom rows are preserved.
    """
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"index_rows": MOCK_INDEX_ROWS_LIST}, message="Index generated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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

    # Fetch sections ordered
    sections_res = (
        await supabase.table("paper_book_sections")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    sections = sections_res.data or []

    # Fetch all documents
    docs_res = (
        await supabase.table("paper_book_documents")
        .select("*")
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

    # Delete existing non-custom rows
    await supabase.table("paper_book_index_rows").delete().eq(
        "paper_book_id", paper_book_id
    ).eq("is_custom", False).execute()

    # Compute page numbers
    rows = compute_page_numbers(sections, docs_by_section)

    if not rows:
        return []

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
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"index_rows": MOCK_INDEX_ROWS_LIST}, message="Index rows fetched successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    response = {"index_rows": res.data or []}
    return Success(data=response, message="Index rows fetched successfully")


@indexRowsRouter.post("/rows/", dependencies=[Depends(AuthenticationRequired)])
async def create_index_row(
    request: Request,
    paper_book_id: str,
    payload: IndexRowCreate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        **MOCK_INDEX_ROW,
        "paper_book_id": paper_book_id,
        "section_id": payload.section_id,
        "sl_no": payload.sl_no,
        "particulars": payload.particulars,
        "page_start_part1": payload.page_start_part1,
        "page_end_part1": payload.page_end_part1,
        "page_start_part2": payload.page_start_part2,
        "page_end_part2": payload.page_end_part2,
        "remarks": payload.remarks,
        "order_index": payload.order_index if payload.order_index is not None else 1,
        "is_custom": True,
        "is_edited": False,
    }
    return Success(data={"index_row": [mock_created]}, message="Index row created successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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

    if payload.order_index is not None:
        order_index = payload.order_index
    else:
        res = (
            await supabase.table("paper_book_index_rows")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        max_order = res.data[0]["order_index"] if res.data else 0
        order_index = max_order + 1

    insert_data = {
        "paper_book_id": paper_book_id,
        "section_id": payload.section_id,
        "sl_no": payload.sl_no,
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
    response = {"index_row": res.data}
    return Success(data=response, message="Index row created successfully")


@indexRowsRouter.patch("/rows/{row_id}/", dependencies=[Depends(AuthenticationRequired)])
async def update_index_row(
    request: Request,
    paper_book_id: str,
    row_id: str,
    payload: IndexRowUpdate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    update_fields = payload.model_dump(exclude_none=True)
    mock_updated = {**MOCK_INDEX_ROW, "id": row_id, "paper_book_id": paper_book_id, **update_fields, "is_edited": True}
    return Success(data={"index_row": [mock_updated]}, message="Index row updated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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

    update_data = payload.model_dump(exclude_none=True)

    # Mark as manually edited
    update_data["is_edited"] = True

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
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={}, message="Index row deleted successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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

    await supabase.table("paper_book_index_rows").delete().eq("id", row_id).execute()

    response = {}
    return Success(data=response, message="Index row deleted successfully")


@indexRowsRouter.patch("/reorder/", dependencies=[Depends(AuthenticationRequired)])
async def reorder_index(
    request: Request,
    paper_book_id: str,
    payload: IndexReorder,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_reordered = [
        {**MOCK_INDEX_ROWS_LIST[idx % len(MOCK_INDEX_ROWS_LIST)], "id": row_id, "order_index": idx + 1}
        for idx, row_id in enumerate(payload.ordered_ids)
    ]
    return Success(data={"index_rows": mock_reordered}, message="Index rows reordered successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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

    updated = []
    for idx, row_id in enumerate(payload.ordered_ids):
        res = (
            supabase.table("paper_book_index_rows")
            .update({"order_index": idx + 1})
            .eq("id", row_id)
            .eq("paper_book_id", paper_book_id)
            .execute()
        )
        if res.data:
            updated.append(res.data[0])

    response = {"index_rows": updated}
    return Success(data=response, message="Index rows reordered successfully")
