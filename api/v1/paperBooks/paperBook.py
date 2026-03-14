import io
from weasyprint import HTML as WeasyHTML
from fastapi import APIRouter, Depends, Request
from app.schemas.requests import PaperBookUpdate
from core.config import config
from core.dependencies import AuthenticationRequired
from core.responseTypes import Success, NotFound
from core.supabase.client import get_supabase_client
from pypdf import PdfReader, PdfWriter


paperBooksRouter = APIRouter()


def build_index_pdf(paper_book: dict, index_rows: list) -> bytes:
    """
    Build the index page as a PDF using WeasyPrint.
    - Supreme Court of India: Part 1 / Part II two-column page number format
    - All other forums: single PAGE NO. column format
    - header_html and footer_html are Tiptap HTML strings stored on paper_book
    - "INDEX" title and the index table are always rendered by code
    - Footer is rendered just below the table (flow position)
    """
 
    is_supreme_court = (
        (paper_book.get("forum") or "").strip().lower() == "supreme court of india"
    )
 
    # ── Helper ───────────────────────────────────────────────────────────────
    def fmt_range(start, end):
        if start is None:
            return ""
        if end is not None and end != start:
            return f"{start}-{end}"
        return str(start)
 
    # ── Header / Footer HTML ─────────────────────────────────────────────────
    header_html = paper_book.get("header_html") or ""
    footer_html = paper_book.get("footer_html") or ""
 
    # ── Table rows ───────────────────────────────────────────────────────────
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
            # For non-SC: prefer part1 page range, fallback to part2
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
 
    # ── Table HTML ───────────────────────────────────────────────────────────
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
 
    # ── Full HTML document ───────────────────────────────────────────────────
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8"/>
        <style>
            @page {{
                size: A4;
                margin: 2cm 1.5cm 2cm 1.5cm;
            }}
 
            body {{
                font-family: "Times New Roman", Times, serif;
                font-size: 9pt;
                color: #000;
                margin: 0;
                padding: 0;
            }}
 
            .header-block {{
                margin-bottom: 16px;
            }}
 
            .header-block p {{
                margin: 2px 0;
                padding: 0;
            }}
 
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

            /* Supreme Court column widths */
            table.index-table col.col-slno        {{ width: 1.2cm; }}
            table.index-table col.col-particulars  {{ width: 9.5cm; }}
            table.index-table col.col-part1        {{ width: 2.8cm; }}
            table.index-table col.col-part2        {{ width: 2.8cm; }}
            table.index-table col.col-remarks      {{ width: 2.5cm; }}
 
            /* Non-Supreme Court column widths */
            table.index-table col.col-pageno       {{ width: 3cm; }}
 
            table.index-table .roman-row td {{
                text-align: center;
                background-color: #F5F5F5;
                font-size: 8pt;
            }}
 
            .footer-block {{
                margin-top: 24px;
            }}
 
            .footer-block p {{
                margin: 2px 0;
                padding: 0;
            }}
        </style>
    </head>
    <body>
 
        <div class="header-block">
            {header_html}
        </div>
 
        <div class="index-title">INDEX</div>
 
        {table_html}
 
        <div class="footer-block">
            {footer_html}
        </div>
 
    </body>
    </html>
    """
 
    pdf_bytes = WeasyHTML(string=html).write_pdf()
    return pdf_bytes

async def merge_pdfs_with_bookmarks(
    index_pdf_bytes: bytes,
    document_paths_ordered: list,
    bookmarks: list,
    supabase,
) -> bytes:
    """
    Merge index PDF + all document PDFs, embed bookmarks.
    bookmarks: list of {title, page_number} — page_number is 1-based in the final merged PDF.
    The index page(s) are prepended, so all bookmark page numbers are offset by index page count.
    """
    writer = PdfWriter()

    # Add index pages
    index_reader = PdfReader(io.BytesIO(index_pdf_bytes))
    index_page_count = len(index_reader.pages)
    for page in index_reader.pages:
        writer.add_page(page)

    # Add document pages in order
    for storage_path in document_paths_ordered:
        try:
            pdf_bytes = await supabase.storage.from_(config.SUPABASE_PREFILING_STORAGE_BUCKET).download(storage_path)
            reader = PdfReader(io.BytesIO(pdf_bytes))
            for page in reader.pages:
                writer.add_page(page)
        except Exception:
            # Skip unreadable files gracefully
            continue

    # Add bookmarks (outline entries)
    # page_number in bookmarks is 1-based in the content (after index),
    # but pypdf uses 0-based page index in the full merged PDF.
    for bm in bookmarks:
        # bm["page_number"] is 1-based page in the document portion
        # offset by index pages to get position in full PDF
        page_idx = (bm["page_number"] - 1) + index_page_count
        total_pages = len(writer.pages)
        if 0 <= page_idx < total_pages:
            print(f"Adding bookmark '{bm['title']}' at page {page_idx + 1} of {total_pages}")
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

    # Fetch index rows
    index_res = (
        await supabase.table("paper_book_index_rows")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    index_rows = index_res.data or []

    if not index_rows:
        raise NotFound(message="No index rows found. Please generate the index first.")

    # Fetch documents ordered by section order + document order
    sections_res = (
        await supabase.table("paper_book_sections")
        .select("id, order_index")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    section_order = {s["id"]: s["order_index"] for s in (sections_res.data or [])}

    docs_res = (
        await supabase.table("paper_book_documents")
        .select("doc_id, section_id, order_index")
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    docs = docs_res.data or []

    # Sort: first by section order, then by document order within section
    docs_sorted = sorted(
        docs,
        key=lambda d: (
            section_order.get(d.get("section_id"), 9999),
            d.get("order_index", 0)
        )
    )

    doc_ids = [d["doc_id"] for d in docs_sorted]

    # Fetch storage paths with id included
    storage_paths_res = (
        await supabase.table("paper_book_files")
        .select("id, storage_path")
        .in_("id", doc_ids)
        .execute()
    )

    storage_paths_data = storage_paths_res.data or []

    # Create mapping: id -> storage_path
    storage_path_map = {
        row["id"]: row["storage_path"]
        for row in storage_paths_data
    }

    # Rebuild list in sorted order
    storage_paths = [
        storage_path_map.get(doc_id)
        for doc_id in doc_ids
        if doc_id in storage_path_map
    ]

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

    # Merge everything
    final_pdf = await merge_pdfs_with_bookmarks(index_pdf, storage_paths, bookmarks, supabase)

    # Update status
    await supabase.from_("paper_books").update({"status": "completed"}).eq("id", paper_book_id).execute()

    return final_pdf



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
    """Stream the merged PDF for in-browser preview (inline)."""
    supabase = await get_supabase_client(request.state.token)
    final_pdf = await build_final_pdf(paper_book_id, request.state.sub, supabase)

    file_path = f"{request.state.sub}/{paper_book_id}/final.pdf"

    await supabase.storage.from_(config.SUPABASE_PREFILING_STORAGE_BUCKET).upload(
        file_path,
        final_pdf,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )

    signed_url = await supabase.storage.from_(
        config.SUPABASE_PREFILING_STORAGE_BUCKET
    ).create_signed_url(file_path, 3600)  # valid for 1 hour

    return Success(data={"url": signed_url["signedURL"]}, message="PDF generated successfully")
