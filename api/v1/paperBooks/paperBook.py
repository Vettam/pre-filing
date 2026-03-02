from fastapi import APIRouter, Depends, Request
from app.schemas.requests import PaperBookUpdate
from core.dependencies import AuthenticationRequired
from core.responseTypes import Success, NotFound
from core.supabase.client import get_supabase_client

paperBooksRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_PAPER_BOOK = {
    "id": "pb-001",
    "title": "SLP in the matter of ABC vs Union of India",
    "forum": "Supreme Court of India",
    "application_type": "Special Leave Petition",
    "client_name": "ABC Pvt Ltd",
    "status": "draft",
    "user_id": "user-001",
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

# ---------------------------------------------------------------------------


@paperBooksRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def get_paper_book(
    paper_book_id: str,
    request: Request,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"paper_book": [MOCK_PAPER_BOOK]}, message="Paper book retrieved successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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
    # ── MOCK ────────────────────────────────────────────────────────────────
    update_fields = payload.model_dump(exclude_none=True)
    mock_updated = {**MOCK_PAPER_BOOK, "id": paper_book_id, **update_fields}
    return Success(data={"paper_book": [mock_updated]}, message="Paper book updated successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

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
