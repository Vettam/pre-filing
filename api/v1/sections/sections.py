from fastapi import APIRouter, Depends, Request
from typing import List
from app.schemas.requests import SectionUpdate
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound

sectionsRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_SECTION = {
    "id": "sec-001",
    "paper_book_id": "pb-001",
    "name": "0/R on Limitation",
    "order_index": 1,
    "page_number_column": "part1",
    "is_default": True,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

MOCK_SECTION_DOCUMENTS = [
    {
        "id": "doc-001",
        "paper_book_id": "pb-001",
        "section_id": "sec-001",
        "doc_id": "d-001",
        "user_id": "u-001",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "doc-002",
        "paper_book_id": "pb-001",
        "section_id": "sec-001",
        "doc_id": "d-002",
        "user_id": "u-001",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

# ---------------------------------------------------------------------------

@sectionsRouter.get("/documents", dependencies=[Depends(AuthenticationRequired)])
async def get_section_documents(
    request: Request,
    paper_book_id: str,
    section_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"section": MOCK_SECTION_DOCUMENTS}, message="Section fetched successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    section_docs = (
        await supabase.table("paper_book_documents")
        .select("id")
        .eq("paper_book_id", paper_book_id)
        .eq("section_id", section_id)
        .eq("user_id", request.state.sub)
        .execute()
    )

    response = {"section": section_docs.data}
    return Success(data=response, message="Section documents retrieved successfully")


@sectionsRouter.patch("/", dependencies=[Depends(AuthenticationRequired)])
async def update_section(
    request: Request,
    paper_book_id: str,
    section_id: str,
    payload: SectionUpdate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    update_fields = payload.model_dump(exclude_none=True)
    if "page_number_column" in update_fields and hasattr(update_fields["page_number_column"], "value"):
        update_fields["page_number_column"] = update_fields["page_number_column"].value
    mock_updated = {**MOCK_SECTION, "id": section_id, "paper_book_id": paper_book_id, **update_fields}
    return Success(data={"section": [mock_updated]}, message="Section updated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    paper_books = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not paper_books.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_sections")
        .select("*")
        .eq("id", section_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Section not found")

    update_data = payload.model_dump(exclude_none=True)
    if "page_number_column" in update_data:
        update_data["page_number_column"] = update_data["page_number_column"].value

    res = (
        await supabase.table("paper_book_sections")
        .update(update_data)
        .eq("id", section_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )
    response = {"section": res.data}
    return Success(data=response, message="Section updated successfully")


@sectionsRouter.delete("/", dependencies=[Depends(AuthenticationRequired)])
async def delete_section(
    request: Request,
    paper_book_id: str,
    section_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={}, message="Section deleted successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    paper_books = (
        await supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not paper_books.data:
        raise NotFound(message="Paper book not found")

    res = (
        await supabase.table("paper_book_sections")
        .select("*")
        .eq("id", section_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Section not found")

    res = (
        await supabase.table("paper_book_sections")
        .delete()
        .eq("id", section_id)
        .execute()
    )
    return Success(data={}, message="Section deleted successfully")
