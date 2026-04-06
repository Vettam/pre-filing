import io
from weasyprint import HTML as WeasyHTML
from fastapi import APIRouter, Depends, Request
from app.schemas.requests import PaperBookUpdate
from core.config import config
from core.dependencies import AuthenticationRequired
from core.responseTypes import Success, NotFound
from core.supabase.client import get_supabase_client
from pypdf import PdfReader, PdfWriter, Transformation
from pypdf.generic import RectangleObject
from reportlab.pdfgen import canvas


paperBooksRouter = APIRouter()


A4_WIDTH  = 595.276  # points
A4_HEIGHT = 841.890  # points


def build_index_pdf(paper_book: dict, index_rows: list) -> bytes:
    """
    Build the index page as a PDF using WeasyPrint.
    - Supreme Court of India: Part 1 / Part II two-column page number format
    - All other forums: single PAGE NO. column format
    - header and footer are Tiptap HTML strings stored on paper_book
    - "INDEX" title and the index table are always rendered by code
    - Footer is rendered just below the table (flow position)
    """

    is_supreme_court = (
        (paper_book.get("forum") or "").strip().lower() == "supreme court of india"
    )

    def fmt_range(start, end):
        if start is None:
            return ""
        if end is not None and end != start:
            return f"{start}-{end}"
        return str(start)

    header_html = paper_book.get("header") or ""
    footer_html = paper_book.get("footer") or ""

    data_rows_html = ""

    if is_supreme_court:
        for row in index_rows:
            part1 = fmt_range(row.get("page_start_part1"), row.get("page_end_part1"))
            part2 = fmt_range(row.get("page_start_part2"), row.get("page_end_part2"))

            particulars = f"<strong>{row.get('particulars', '')}</strong>"
            if row.get("remarks"):
                particulars += f"<br/><span style='font-size:7pt;'>{row['remarks']}</span>"

            data_rows_html += f"""
            <tr>
                <td style="text-align:center;">{row.get("sl_no") or ""}</td>
                <td>{particulars}</td>
                <td style="text-align:center;">{part1}</td>
                <td style="text-align:center;">{part2}</td>
                <td></td>
            </tr>
            """
    else:
        for row in index_rows:
            page_start = row.get("page_start_part1") or row.get("page_start_part2")
            page_end   = row.get("page_end_part1")   or row.get("page_end_part2")
            page_no    = fmt_range(page_start, page_end)

            particulars = row.get("particulars", "")
            if row.get("remarks"):
                particulars += f"<br/><span style='font-size:7pt;'>{row['remarks']}</span>"

            data_rows_html += f"""
            <tr>
                <td>{row.get("sl_no") or ""}</td>
                <td>{particulars}</td>
                <td style="text-align:center;">{page_no}</td>
            </tr>
            """

    if is_supreme_court:
        table_html = f"""
        <table class="index-table">
            <colgroup>
                <col class="col-slno"/>
                <col class="col-particulars"/>
                <col class="col-part1"/>
                <col class="col-part2"/>
                <col class="col-remarks"/>
            </colgroup>
            <thead>
                <tr>
                    <th rowspan="2">Sl.no</th>
                    <th rowspan="2">Particulars of Document</th>
                    <th colspan="2">Page No. of part to which it belongs</th>
                    <th rowspan="2">Remarks</th>
                </tr>
                <tr>
                    <th>Part 1<br/>(Contents of<br/>Paper Book)</th>
                    <th>Part II<br/>(Contents of<br/>file alone)</th>
                </tr>
                <tr class="roman-row">
                    <td>i</td>
                    <td>ii</td>
                    <td>iii</td>
                    <td>iv</td>
                    <td>v</td>
                </tr>
            </thead>
            <tbody>
                {data_rows_html}
            </tbody>
        </table>
        """
    else:
        table_html = f"""
        <table class="index-table">
            <colgroup>
                <col class="col-slno"/>
                <col class="col-particulars"/>
                <col class="col-pageno"/>
            </colgroup>
            <thead>
                <tr>
                    <th>S.NO.</th>
                    <th>PARTICULARS</th>
                    <th>PAGE NO.</th>
                </tr>
            </thead>
            <tbody>
                {data_rows_html}
            </tbody>
        </table>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"/>
        <style>
            @page {{
                size: A4;
                margin: 2cm 2cm 2cm 2cm;
            }}
            body {{
                font-family: "Times New Roman", Times, serif;
                font-size: 9pt;
                color: #000;
                margin: 0;
                padding: 0;
            }}
            .header-block {{ margin-bottom: 16px; }}
            .header-block p {{ margin: 2px 0; padding: 0; }}
            .index-title {{
                text-align: center;
                font-weight: bold;
                font-size: 10pt;
                margin: 16px 0 8px 0;
                letter-spacing: 1px;
            }}
            table.index-table {{
                width: 100%;
                border-collapse: collapse;
                font-size: 8pt;
            }}
            table.index-table th,
            table.index-table td {{
                border: 0.5px solid #000;
                padding: 5px 4px;
                vertical-align: top;
            }}
            table.index-table th {{
                font-weight: bold;
                text-align: center;
                background-color: #fff;
            }}
            table.index-table col.col-slno        {{ width: 1.2cm; }}
            table.index-table col.col-particulars  {{ width: 8.5cm; }}
            table.index-table col.col-part1        {{ width: 2.5cm; }}
            table.index-table col.col-part2        {{ width: 2.5cm; }}
            table.index-table col.col-remarks      {{ width: 2.3cm; }}
            table.index-table col.col-pageno       {{ width: 3cm; }}
            table.index-table .roman-row td {{
                text-align: center;
                background-color: #F5F5F5;
                font-size: 8pt;
            }}
            .footer-block {{ margin-top: 24px; }}
            .footer-block p {{ margin: 2px 0; padding: 0; }}
        </style>
    </head>
    <body>
        <div class="header-block">{header_html}</div>
        <div class="index-title">INDEX</div>
        {table_html}
        <div class="footer-block">{footer_html}</div>
    </body>
    </html>
    """

    pdf_bytes = WeasyHTML(string=html).write_pdf()
    return pdf_bytes


def build_page_label_sequence(index_rows: list, docs_by_section: dict) -> list[str]:
    """
    Build a flat ordered list of page labels — one label per page across
    all documents in section order.

    Rules per page_label_style:
      - numeric:       1, 2, 3 ...
      - roman:         i, ii, iii ...
      - alpha_only:    A, A, A ... (same label repeated for every page)
      - alpha_numeric: A1, A2, A3 ...
      - none / null:   treated as numeric

    Page number source: page_start_part1 from index row (already computed).
    Page count per section: sum of page_count from joined paper_book_files.

    For sections with no documents or no page_start_part1 → skip (no labels).
    """

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

    def parse_label_start(label: str | None) -> tuple[str | None, str | None, int | None]:
        """
        Parse a label like 'A1', 'NS3', 'A', 'B', '5', 'iv' into
        (prefix, style_hint, numeric_part).
        Returns (prefix, numeric_part_str) or (None, None) if unparseable.
        """
        if not label:
            return None, None
        # Try pure integer
        try:
            return None, int(label)
        except ValueError:
            pass
        # Try roman
        roman_map = {
            "i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5,
            "vi": 6, "vii": 7, "viii": 8, "ix": 9, "x": 10,
            "xi": 11, "xii": 12, "xiii": 13, "xiv": 14, "xv": 15,
        }
        if label.lower() in roman_map:
            return "roman", roman_map[label.lower()]
        # Try alpha_numeric: extract leading alpha prefix and trailing number
        import re
        match = re.match(r'^([A-Za-z]+)(\d+)$', label)
        if match:
            return match.group(1), int(match.group(2))
        # Pure alpha (alpha_only) — e.g. "A", "B", "NS"
        return label, None

    labels = []

    for row in index_rows:
        section_id  = row.get("section_id")
        style       = row.get("page_label_style") or "numeric"
        prefix      = row.get("page_label_prefix")

        # Use part1 label as the overlay source (per user confirmation)
        start_label = row.get("page_start_part1") or row.get("page_start_part2")

        if not start_label:
            # Section has no page number — skip, no overlay for its pages
            # But we still need to account for its pages in the flat list
            docs = docs_by_section.get(section_id, [])
            page_count = _sum_page_counts(docs)
            labels.extend([""] * page_count)
            continue

        docs = docs_by_section.get(section_id, [])
        page_count = _sum_page_counts(docs)

        if page_count == 0:
            continue

        parsed_prefix, parsed_num = parse_label_start(start_label)

        if style == "alpha_only":
            # Same label on every page of this section
            labels.extend([start_label] * page_count)

        elif style == "alpha_numeric":
            # prefix + incrementing number starting from parsed_num
            start_num = parsed_num if parsed_num is not None else 1
            for i in range(page_count):
                labels.append(f"{parsed_prefix}{start_num + i}")

        elif style == "roman":
            start_num = parsed_num if parsed_num is not None else 1
            for i in range(page_count):
                labels.append(to_roman(start_num + i))

        else:
            # numeric (default, also covers "none")
            start_num = parsed_num if parsed_num is not None else 1
            for i in range(page_count):
                labels.append(str(start_num + i))

    return labels


def _sum_page_counts(docs: list) -> int:
    """Sum page_count from a list of paper_book_documents joined with paper_book_files."""
    total = 0
    for doc in docs:
        files = doc.get("paper_book_files")
        pc = None
        if isinstance(files, dict):
            pc = files.get("page_count")
        elif isinstance(files, list) and files:
            pc = files[0].get("page_count")
        if pc:
            total += pc
    return total


def overlay_page_label(page, label: str) -> object:
    """
    Overlay a page label string at the top-right of a PDF page
    using ReportLab, then merge it onto the existing page.
    Font: Times-Roman 12pt, top-right position.
    """
    if not label:
        return page

    # Get page dimensions
    page_width  = float(page.mediabox.width)
    page_height = float(page.mediabox.height)

    # Build a transparent overlay PDF with just the label
    overlay_buf = io.BytesIO()
    c = canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))
    c.setFont("Times-Roman", 12)

    # Top-right: 1.5cm from right edge, 1cm from top
    right_margin = 42.52   # ~1.5cm in points
    top_margin   = 28.35   # ~1cm in points
    text_width   = c.stringWidth(label, "Times-Roman", 12)
    x = page_width - right_margin - text_width
    y = page_height - top_margin  # near top instead of bottom

    c.drawString(x, y, label)
    c.save()

    overlay_buf.seek(0)
    overlay_reader = PdfReader(overlay_buf)
    overlay_page   = overlay_reader.pages[0]

    # Merge overlay onto the original page
    page.merge_page(overlay_page)
    return page


def normalize_page_to_a4(page):
    """
    Resize and center any PDF page to A4 dimensions.
    If the page is already A4, returns it unchanged.
    Scales content proportionally to fit within A4, centered.
    """
    original_width  = float(page.mediabox.width)
    original_height = float(page.mediabox.height)
 
    # Skip if already A4 (within 1pt tolerance)
    if (
        abs(original_width  - A4_WIDTH)  < 1.0 and
        abs(original_height - A4_HEIGHT) < 1.0
    ):
        return page
 
    # Compute scale to fit within A4 while preserving aspect ratio
    scale = min(A4_WIDTH / original_width, A4_HEIGHT / original_height)
 
    # Compute offsets to center the scaled content on A4
    scaled_width  = original_width  * scale
    scaled_height = original_height * scale
    offset_x = (A4_WIDTH  - scaled_width)  / 2
    offset_y = (A4_HEIGHT - scaled_height) / 2
 
    # Apply scale + translation transform to the page content
    transform = Transformation().scale(scale, scale).translate(offset_x, offset_y)
    page.add_transformation(transform)
 
    # Set the mediabox to A4
    page.mediabox = RectangleObject((0, 0, A4_WIDTH, A4_HEIGHT))
 
    return page
 
 
async def merge_pdfs_with_bookmarks(
    index_pdf_bytes: bytes,
    document_paths_ordered: list,
    bookmarks: list,
    index_rows: list,
    docs_by_section: dict,
    supabase,
) -> bytes:
    """
    Merge index PDF + all document PDFs, embed bookmarks,
    and overlay page labels on every document page (not on index pages).
    All pages are normalized to A4 size before merging.
    """
    writer = PdfWriter()
 
    # ── Add index pages (no overlay, already A4 from WeasyPrint) ─────────────
    index_reader     = PdfReader(io.BytesIO(index_pdf_bytes))
    index_page_count = len(index_reader.pages)
    for page in index_reader.pages:
        writer.add_page(page)
 
    # ── Build flat label sequence ─────────────────────────────────────────────
    page_labels = build_page_label_sequence(index_rows, docs_by_section)
    label_idx   = 0
 
    # ── Add document pages with A4 normalization and overlay ─────────────────
    for storage_path in document_paths_ordered:
        try:
            pdf_bytes = await supabase.storage.from_(
                config.SUPABASE_PREFILING_STORAGE_BUCKET
            ).download(storage_path)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                # Normalize to A4 first, then overlay label
                page  = normalize_page_to_a4(page)
                label = page_labels[label_idx] if label_idx < len(page_labels) else ""
                page  = overlay_page_label(page, label)
                writer.add_page(page)
                label_idx += 1
        except Exception:
            continue
 
    # ── Add bookmarks (outline entries) ──────────────────────────────────────
    for bm in bookmarks:
        page_idx    = (bm["page_number"] - 1) + index_page_count
        total_pages = len(writer.pages)
        if 0 <= page_idx < total_pages:
            writer.add_outline_item(title=bm["title"], page_number=page_idx)
 
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


async def build_final_pdf(paper_book_id: str, user_id: str, supabase) -> bytes:
    paper_book = (
        await supabase.table("paper_books")
        .select("*")
        .eq("id", paper_book_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not paper_book.data:
        raise NotFound(message="Paper book not found")

    # Fetch index rows (includes page_label_style and page_label_prefix)
    index_res = (
        await supabase.table("paper_book_index_rows")
        .select("*, paper_book_sections(page_label_style, page_label_prefix, page_number_column)")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    index_rows = index_res.data or []

    if not index_rows:
        raise NotFound(message="No index rows found. Please generate the index first.")

    # Flatten page_label_style and page_label_prefix from joined section onto each row
    for row in index_rows:
        section_data = row.pop("paper_book_sections", None) or {}
        row.setdefault("page_label_style",  section_data.get("page_label_style") or "numeric")
        row.setdefault("page_label_prefix", section_data.get("page_label_prefix"))

    # Fetch sections ordered
    sections_res = (
        await supabase.table("paper_book_sections")
        .select("id, order_index")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    section_order = {s["id"]: s["order_index"] for s in (sections_res.data or [])}

    # Fetch documents with page_count joined
    docs_res = (
        await supabase.table("paper_book_documents")
        .select("id, doc_id, section_id, order_index, paper_book_files(page_count, storage_path)")
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    docs = docs_res.data or []

    # Sort docs: section order → document order
    docs_sorted = sorted(
        docs,
        key=lambda d: (
            section_order.get(d.get("section_id"), 9999),
            d.get("order_index", 0)
        )
    )

    # Build docs_by_section for label sequence computation
    docs_by_section: dict = {}
    for doc in docs_sorted:
        sid = doc.get("section_id")
        if sid:
            docs_by_section.setdefault(sid, []).append(doc)

    # Build ordered storage paths
    storage_paths = []
    for doc in docs_sorted:
        files = doc.get("paper_book_files")
        sp = None
        if isinstance(files, dict):
            sp = files.get("storage_path")
        elif isinstance(files, list) and files:
            sp = files[0].get("storage_path")
        if sp:
            storage_paths.append(sp)

    # Fetch bookmarks
    bookmarks_res = (
        await supabase.table("paper_book_bookmarks")
        .select("title, page_number")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    bookmarks = bookmarks_res.data or []

    # Build index PDF
    index_pdf = build_index_pdf(paper_book.data, index_rows)

    # Merge everything with page label overlays
    final_pdf = await merge_pdfs_with_bookmarks(
        index_pdf_bytes        = index_pdf,
        document_paths_ordered = storage_paths,
        bookmarks              = bookmarks,
        index_rows             = index_rows,
        docs_by_section        = docs_by_section,
        supabase               = supabase,
    )

    # Update status
    await supabase.from_("paper_books").update({"status": "completed"}).eq(
        "id", paper_book_id
    ).execute()

    return final_pdf, paper_book.data["title"]


@paperBooksRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def get_paper_book(
    paper_book_id: str,
    request: Request,
):
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("*")
        .eq("id", paper_book_id)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    response = {"paper_book": res.data}
    return Success(data=response, message="Paper book retrieved successfully")


@paperBooksRouter.patch("/", dependencies=[Depends(AuthenticationRequired)])
async def update_paper_book(
    paper_book_id: str,
    payload: PaperBookUpdate,
    request: Request,
):
    supabase = await get_supabase_client(request.state.token)
    update_data = payload.model_dump(exclude_none=True)
    res = (
        await supabase.table("paper_books")
        .update(update_data)
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    response = {"paper_book": res.data}
    return Success(data=response, message="Paper book updated successfully")


@paperBooksRouter.delete("/", dependencies=[Depends(AuthenticationRequired)])
async def delete_paper_book(
    paper_book_id: str,
    request: Request,
):
    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .update({"deleted_at": "now()"})
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    response = {"paper_book": res.data}
    return Success(data=response, message="Paper book deleted successfully")


@paperBooksRouter.get("/export/", dependencies=[Depends(AuthenticationRequired)])
async def preview_pdf(
    request: Request,
    paper_book_id: str,
):
    """Build, upload and return a signed URL for the final merged PDF."""
    supabase   = await get_supabase_client(request.state.token)
    final_pdf, paper_book_title  = await build_final_pdf(paper_book_id, request.state.sub, supabase)
    file_path  = f"{request.state.sub}/{paper_book_id}/{paper_book_title}.pdf"

    await supabase.storage.from_(config.SUPABASE_PREFILING_STORAGE_BUCKET).upload(
        file_path,
        final_pdf,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )

    signed_url = await supabase.storage.from_(
        config.SUPABASE_PREFILING_STORAGE_BUCKET
    ).create_signed_url(file_path, 3600)

    return Success(data={"url": signed_url["signedURL"]}, message="PDF generated successfully")
