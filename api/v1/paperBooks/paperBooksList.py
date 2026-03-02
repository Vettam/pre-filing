from fastapi import APIRouter, Depends, Request
from app.schemas.requests import PaperBookCreate
from core.dependencies import AuthenticationRequired
from core.responseTypes import Success
from core.supabase.client import get_supabase_client

paperBooksListRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_PAPER_BOOKS_LIST = [
    {
        "id": "pb-001",
        "title": "SLP in the matter of ABC vs Union of India",
        "forum": "Supreme Court of India",
        "application_type": "Special Leave Petition",
        "client_name": "ABC Pvt Ltd",
        "status": "draft",
        "user_id": "user-001",
        "created_at": "2025-01-03T00:00:00+00:00",
        "updated_at": "2025-01-03T00:00:00+00:00",
    },
    {
        "id": "pb-002",
        "title": "Writ Petition - XYZ vs State of Maharashtra",
        "forum": "Bombay High Court",
        "application_type": "Writ Petition",
        "client_name": "XYZ Ltd",
        "status": "index_created",
        "user_id": "user-001",
        "created_at": "2025-01-02T00:00:00+00:00",
        "updated_at": "2025-01-02T00:00:00+00:00",
    },
    {
        "id": "pb-003",
        "title": "Income Tax Appeal - PQR Industries",
        "forum": "Income Tax Appellate Tribunal",
        "application_type": "Appeal",
        "client_name": None,
        "status": "completed",
        "user_id": "user-001",
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

MOCK_PAPER_BOOK_CREATED = {
    "id": "pb-004",
    "title": "",
    "forum": "",
    "application_type": "",
    "client_name": None,
    "status": "draft",
    "user_id": "user-001",
    "created_at": "2025-01-04T00:00:00+00:00",
    "updated_at": "2025-01-04T00:00:00+00:00",
}

# ---------------------------------------------------------------------------


@paperBooksListRouter.post("/", dependencies=[Depends(AuthenticationRequired)])
async def create_paper_book(
    request: Request,
    payload: PaperBookCreate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        **MOCK_PAPER_BOOK_CREATED,
        "title": payload.title,
        "forum": payload.forum,
        "application_type": payload.application_type,
        "client_name": payload.client_name,
    }
    return Success(data={"paper_book": mock_created}, message="Paper book created successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)

    # Create the paper book
    pb_res = (
        await supabase.from_("paper_books")
        .insert({
            "title": payload.title,
            "forum": payload.forum,
            "application_type": payload.application_type,
            "client_name": payload.client_name,
            "user_id": request.state.sub,
            "status": "draft",
        })
        .execute()
    )
    paper_book = pb_res.data[0]
    paper_book_id = paper_book["id"]

    # Auto-create default sections
    defaults_res = (
        await supabase.from_("paper_book_default_sections")
        .select("*")
        .order("order_index")
        .execute()
    )
    default_sections = defaults_res.data or []

    if default_sections:
        sections_to_insert = [
            {
                "paper_book_id": paper_book_id,
                "name": s["name"],
                "order_index": s["order_index"],
                "page_number_column": s["page_number_column"],
                "is_default": True,
            }
            for s in default_sections
        ]
        await supabase.from_("paper_book_sections").insert(sections_to_insert).execute()

    response = {"paper_book": paper_book}
    return Success(data=response, message="Paper book created successfully")


@paperBooksListRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def list_paper_books(
    request: Request,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"paper_books": MOCK_PAPER_BOOKS_LIST}, message="Paper books retrieved successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        await supabase.from_("paper_books")
        .select("*")
        .eq("user_id", request.state.sub)
        .order("created_at", desc=True)
        .execute()
    )
    response = {"paper_books": res.data}
    return Success(data=response, message="Paper books retrieved successfully")
