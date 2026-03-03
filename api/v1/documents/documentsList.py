import io
import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pypdf import PdfReader, PdfWriter
from app.constants import VALID_FILE_FORMATS
from app.utils import normalize_supabase_storage_key, encode_url_path
from app.schemas.requests import (
    DocumentCreate, DocumentUpdate, DocumentAssignSection,
    DocumentReorder, DocumentSplitRequest, CommitDocumentUpload,
)
from core.config import config
from core.dependencies import AuthenticationRequired
from core.logging import logger
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound, BadRequest


router = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_DOCUMENT = {
    "id": "pbd-001",
    "paper_book_id": "pb-001",
    "doc_id": "doc-001",
    "section_id": "sec-001",
    "order_index": 1,
    "is_split_child": False,
    "parent_document_id": None,
    "split_page_start": None,
    "split_page_end": None,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

MOCK_DOCUMENTS_LIST = [
    {
        "id": "pbd-001",
        "paper_book_id": "pb-001",
        "doc_id": "doc-001",
        "section_id": "sec-001",
        "order_index": 1,
        "is_split_child": False,
        "parent_document_id": None,
        "split_page_start": None,
        "split_page_end": None,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "pbd-002",
        "paper_book_id": "pb-001",
        "doc_id": "doc-002",
        "section_id": "sec-001",
        "order_index": 2,
        "is_split_child": False,
        "parent_document_id": None,
        "split_page_start": None,
        "split_page_end": None,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "pbd-003",
        "paper_book_id": "pb-001",
        "doc_id": "doc-003",
        "section_id": "sec-002",
        "order_index": 1,
        "is_split_child": False,
        "parent_document_id": None,
        "split_page_start": None,
        "split_page_end": None,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

MOCK_SPLIT_DOCUMENTS = [
    {
        "id": "pbd-004",
        "paper_book_id": "pb-001",
        "doc_id": "doc-004",
        "section_id": "sec-001",
        "order_index": 1,
        "is_split_child": True,
        "parent_document_id": "pbd-001",
        "split_page_start": 1,
        "split_page_end": 5,
        "storage_path": "paperbook-documents/doc-001_part1.pdf",
        "uploaded_filename": "doc-001_part1.pdf",
        "file_size": 102400,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "pbd-005",
        "paper_book_id": "pb-001",
        "doc_id": "doc-005",
        "section_id": "sec-001",
        "order_index": 2,
        "is_split_child": True,
        "parent_document_id": "pbd-001",
        "split_page_start": 6,
        "split_page_end": 12,
        "storage_path": "paperbook-documents/doc-001_part2.pdf",
        "uploaded_filename": "doc-001_part2.pdf",
        "file_size": 143360,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

# ---------------------------------------------------------------------------


async def upload_pdf_to_storage(supabase, storage_path: str, pdf_bytes: bytes) -> str:
    """Upload PDF bytes to Supabase storage, return the path."""
    try:
        await supabase.storage.from_(config.SUPABASE_STORAGE_BUCKET).upload(
            path=storage_path,
            file=pdf_bytes,
            file_options={"content-type": "application/pdf", "upsert": "true"},
        )
        return storage_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to upload file to storage: {str(e)}")


async def delete_from_storage(supabase, storage_path: str):
    try:
        await supabase.storage.from_(config.SUPABASE_STORAGE_BUCKET).remove([storage_path])
    except Exception:
        pass


@router.post("/", dependencies=[Depends(AuthenticationRequired)])
async def create_document_record(
    request: Request,
    paper_book_id: str,
    payload: DocumentCreate,
):
    """
    FE uploads file directly to Supabase storage,
    then calls this endpoint with the doc_id to create the DB record.
    """
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        **MOCK_DOCUMENT,
        "paper_book_id": paper_book_id,
        "doc_id": payload.doc_id,
        "section_id": payload.section_id,
        "order_index": payload.order_index if payload.order_index is not None else 1,
    }
    return Success(data={"document": [mock_created]}, message="Document record created successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    # Determine order_index within section (or global)
    if payload.order_index is not None:
        order_index = payload.order_index
    else:
        query = (
            supabase.table("paper_book_documents")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
        )
        if payload.section_id:
            query = query.eq("section_id", payload.section_id)

        res = await query.order("order_index", desc=True).limit(1).execute()
        max_order = res.data[0]["order_index"] if res.data else 0
        order_index = max_order + 1

    insert_data = {
        "paper_book_id": paper_book_id,
        "doc_id": payload.doc_id,
        "section_id": payload.section_id,
        "order_index": order_index,
        "is_split_child": False,
    }

    res = await supabase.table("paper_book_documents").insert(insert_data).execute()

    # Update paper book status if still draft
    await supabase.table("paper_books").update({"status": "documents_uploaded"}).eq(
        "id", paper_book_id
    ).eq("status", "draft").execute()

    response = {"document": res.data}
    return Success(data=response, message="Document record created successfully")


@router.get("/", dependencies=[Depends(AuthenticationRequired)])
async def list_documents(
    request: Request,
    paper_book_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"documents": MOCK_DOCUMENTS_LIST}, message="Documents retrieved successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_documents")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )

    response = {"documents": res.data or []}
    return Success(data=response, message="Documents retrieved successfully")


@router.get("/upload/", dependencies=[Depends(AuthenticationRequired)])
async def get_upload_url(
    request: Request,
    paper_book_id: str,
    filename: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    response = {
        "upload_url": "encoded_signed_url",
        "file_path": "file_path",
        "upload_token": "upload_token",
        "paper_book_id": paper_book_id,
    }
    return Success(data=response, message="Upload URL generated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    if "." not in filename:
        return BadRequest(message="File name must include an extension")

    extension = filename.split(".")[-1].lower()
    if extension not in VALID_FILE_FORMATS:
        return BadRequest(message="Invalid file format")

    title = ".".join(filename.split(".")[:-1])
    title = normalize_supabase_storage_key(title)
    date_time = (
        datetime.now(timezone.utc)
        .isoformat()
        .replace(":", "-")
        .replace("+", "-")
        .replace(".", "-")
    )


    # Generate a unique storage path for the new document
    file_path += f"{title}_{date_time}.{extension}"
    storage_path = f"paper-books/{request.state.sub}/{paper_book_id}/{file_path}"

    # Generate signed upload URL (valid for 1 hour = 3600 seconds)
    bucket = supabase.storage.from_(config.SUPABASE_PREFILING_STORAGE_BUCKET)
    upload_url_response = await bucket.create_signed_upload_url(
        path=file_path,
    )

    if not upload_url_response or not upload_url_response.get("signedUrl"):
        logger.error(
            f"Failed to generate signed upload URL: {upload_url_response}"
        )
        raise HTTPException(status_code=500, detail="Failed to generate upload URL")
    
    signed_url = upload_url_response.get("signedUrl")
    upload_token = upload_url_response.get("token")

    # Encode the URL path to handle special characters
    encoded_signed_url = encode_url_path(signed_url)

    response = {
        "upload_url": encoded_signed_url,
        "file_path": file_path,
        "upload_token": upload_token,
        "paper_book_id": paper_book_id,
    }

    return Success(data=response, message="Upload URL generated successfully")


@router.post("/upload/", dependencies=[Depends(AuthenticationRequired)])
async def commit_uploaded_document(
    request: Request,
    paper_book_id: str,
    payload: CommitDocumentUpload,
):
    """
    After FE uploads file to Supabase storage using the signed URL,
    it calls this endpoint to create the DB record for the uploaded document.
    """
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        "paper_book_id": paper_book_id,
        "doc_id": "doc-101",
    }
    return Success(data={"document": [mock_created]}, message="Uploaded document committed successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

@router.patch("/{doc_id}/", dependencies=[Depends(AuthenticationRequired)])
async def update_document(
    request: Request,
    paper_book_id: str,
    doc_id: str,
    payload: DocumentUpdate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    update_fields = payload.model_dump(exclude_none=True)
    mock_updated = {**MOCK_DOCUMENT, "id": doc_id, "paper_book_id": paper_book_id, **update_fields}
    return Success(data={"document": [mock_updated]}, message="Document updated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_documents")
        .select("*")
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Document not found")

    update_data = payload.model_dump(exclude_none=True)

    res = (
        await supabase.table("paper_book_documents")
        .update(update_data)
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    response = {"document": res.data}
    return Success(data=response, message="Document updated successfully")


@router.delete("/{doc_id}/", dependencies=[Depends(AuthenticationRequired)])
async def delete_document(
    request: Request,
    paper_book_id: str,
    doc_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={}, message="Document deleted successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_documents")
        .select("*")
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Document not found")

    doc = res.data[0]

    # Delete from storage
    await delete_from_storage(supabase, doc["storage_path"])

    await supabase.table("paper_book_documents").delete().eq("id", doc_id).execute()

    response = {}
    return Success(data=response, message="Document deleted successfully")


@router.patch("/reorder/", dependencies=[Depends(AuthenticationRequired)])
async def reorder_documents(
    request: Request,
    paper_book_id: str,
    payload: DocumentReorder,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={}, message="Documents reordered successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    for item in payload.items:
        update_data = {"order_index": item.order_index}
        if item.section_id is not None:
            update_data["section_id"] = item.section_id

        await supabase.table("paper_book_documents").update(update_data).eq(
            "id", item.id
        ).eq("paper_book_id", paper_book_id).execute()

    response = {}
    return Success(data=response, message="Documents reordered successfully")


@router.patch("/{doc_id}/assign-section/", dependencies=[Depends(AuthenticationRequired)])
async def assign_section(
    request: Request,
    paper_book_id: str,
    doc_id: str,
    payload: DocumentAssignSection,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_assigned = {
        **MOCK_DOCUMENT,
        "id": doc_id,
        "paper_book_id": paper_book_id,
        "section_id": payload.section_id,
        "order_index": payload.order_index if payload.order_index is not None else 1,
    }
    return Success(data={"document": [mock_assigned]}, message="Document assigned to section successfully")
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
        await supabase.table("paper_book_documents")
        .select("*")
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Document not found")

    # Determine order within new section
    if payload.order_index is not None:
        order_index = payload.order_index
    else:
        res = (
            await supabase.table("paper_book_documents")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .eq("section_id", payload.section_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        max_order = res.data[0]["order_index"] if res.data else 0
        order_index = max_order + 1

    res = (
        await supabase.table("paper_book_documents")
        .update({"section_id": payload.section_id, "order_index": order_index})
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )

    response = {"document": res.data}
    return Success(data=response, message="Document assigned to section successfully")


@router.post("/{doc_id}/split/", dependencies=[Depends(AuthenticationRequired)])
async def split_document(
    request: Request,
    paper_book_id: str,
    doc_id: str,
    payload: DocumentSplitRequest,
):
    """
    Split a PDF into multiple parts based on page ranges.
    The original document is replaced by the split parts.
    Pages not included in any range are discarded.
    """
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_splits = [
        {
            **MOCK_SPLIT_DOCUMENTS[idx % len(MOCK_SPLIT_DOCUMENTS)],
            "parent_document_id": doc_id,
            "paper_book_id": paper_book_id,
            "split_page_start": r.start,
            "split_page_end": r.end,
            "uploaded_filename": r.filename if r.filename else f"document_part{idx + 1}.pdf",
            "order_index": idx + 1,
        }
        for idx, r in enumerate(payload.ranges)
    ]
    return Success(data={"created_documents": mock_splits}, message="Document split successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)

    # Verify paper book ownership
    pb_res = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .execute()
    )
    if not pb_res.data:
        raise NotFound(message="Paper book not found")

    # Fetch paper_book_document record
    pbd_res = (
        await supabase.table("paper_book_documents")
        .select("*")
        .eq("id", doc_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not pbd_res.data:
        raise NotFound(message="Document not found")

    pbd = pbd_res.data  # paper_book_documents row

    # Fetch the actual document from paper_book_files table using doc_id FK
    doc_res = (
        await supabase.table("paper_book_files")
        .select("id, storage_path, uploaded_filename, file_size")
        .eq("doc_id", pbd["doc_id"])
        .single()
        .execute()
    )
    if not doc_res.data:
        raise NotFound(message="Source document record not found")

    original_doc = doc_res.data  # paper_book_files row

    # Validate ranges
    for r in payload.ranges:
        if r.end < r.start:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid range: end ({r.end}) must be >= start ({r.start})",
            )

    # Download original PDF from storage
    pdf_bytes = await supabase.storage.from_(config.SUPABASE_STORAGE_BUCKET).download(original_doc["storage_path"])

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)

    # Validate page numbers against actual page count
    for r in payload.ranges:
        if r.start > total_pages or r.end > total_pages:
            raise HTTPException(
                status_code=400,
                detail=f"Page range {r.start}-{r.end} exceeds document page count ({total_pages})",
            )

    # Derive storage dir and stem from original doc
    original_dir = os.path.dirname(original_doc["storage_path"])
    original_stem = os.path.splitext(os.path.basename(original_doc["storage_path"]))[0]

    created_docs = []

    for idx, r in enumerate(payload.ranges):
        # Build split PDF bytes
        writer = PdfWriter()
        for page_num in range(r.start - 1, r.end):  # convert to 0-based
            writer.add_page(reader.pages[page_num])

        buf = io.BytesIO()
        writer.write(buf)
        split_bytes = buf.getvalue()

        # Determine filename for this part
        if r.filename:
            part_filename = r.filename if r.filename.endswith(".pdf") else f"{r.filename}.pdf"
        else:
            part_filename = f"{original_stem}_part{idx + 1}.pdf"

        # Build storage path
        storage_path = f"{original_dir}/{part_filename}" if original_dir else part_filename
        storage_path = storage_path.replace("//", "/")

        # Upload split PDF to storage
        await upload_pdf_to_storage(supabase, storage_path, split_bytes)

        # Create new record in `paper_book_files` table
        new_doc_res = (
            await supabase.table("paper_book_files")
            .insert({
                "user_id": request.state.sub,
                "title": part_filename,
                "storage_path": storage_path,
                "uploaded_filename": part_filename,
                "file_size": len(split_bytes),
            })
            .execute()
        )
        new_doc = new_doc_res.data[0]  # has the new doc_id

        # Create new record in `paper_book_documents` table
        new_pbd_res = (
            await supabase.table("paper_book_documents")
            .insert({
                "paper_book_id": paper_book_id,
                "section_id": pbd["section_id"],
                "doc_id": new_doc["doc_id"],
                "order_index": pbd["order_index"] + idx,
                "is_split_child": True,
                "parent_document_id": pbd["id"],
                "split_page_start": r.start,
                "split_page_end": r.end,
            })
            .execute()
        )

        created_docs.append({
            **new_pbd_res.data[0],
            "storage_path": storage_path,
            "uploaded_filename": part_filename,
            "file_size": len(split_bytes),
        })

    # Delete original from storage
    await delete_from_storage(supabase, original_doc["storage_path"])

    # Delete original record from `paper_book_files` table
    await supabase.table("paper_book_files").delete().eq("id", original_doc["id"]).execute()

    # Delete original record from `paper_book_documents` table
    await supabase.table("paper_book_documents").delete().eq("id", pbd["id"]).execute()

    return Success(data={"created_documents": created_docs}, message="Document split successfully")
