from fastapi import APIRouter, Depends, Request
from typing import List
from app.schemas.requests import SectionCreate, SectionReorder
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound

sectionsListRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_SECTIONS_LIST = [
    {
        "id": "sec-001",
        "paper_book_id": "pb-001",
        "name": "0/R on Limitation",
        "order_index": 1,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-002",
        "paper_book_id": "pb-001",
        "name": "Listing Performa",
        "order_index": 2,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-003",
        "paper_book_id": "pb-001",
        "name": "Cover page of the paper book",
        "order_index": 3,
        "page_number_column": "part2",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-004",
        "paper_book_id": "pb-001",
        "name": "Index of record of proceedings",
        "order_index": 4,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-005",
        "paper_book_id": "pb-001",
        "name": "Limitation Report prepared by the Registry",
        "order_index": 5,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-006",
        "paper_book_id": "pb-001",
        "name": "Defect List",
        "order_index": 6,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-007",
        "paper_book_id": "pb-001",
        "name": "Note sheet",
        "order_index": 7,
        "page_number_column": "part2",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-008",
        "paper_book_id": "pb-001",
        "name": "List of details",
        "order_index": 8,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-009",
        "paper_book_id": "pb-001",
        "name": "Impugned Order",
        "order_index": 9,
        "page_number_column": "part1",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-010",
        "paper_book_id": "pb-001",
        "name": "SLP with affidavit",
        "order_index": 10,
        "page_number_column": "both",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-011",
        "paper_book_id": "pb-001",
        "name": "Appendix",
        "order_index": 11,
        "page_number_column": "both",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-012",
        "paper_book_id": "pb-001",
        "name": "Annexure P-1",
        "order_index": 12,
        "page_number_column": "both",
        "is_default": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "sec-013",
        "paper_book_id": "pb-001",
        "name": "Custom Section Added by User",
        "order_index": 13,
        "page_number_column": "part1",
        "is_default": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

MOCK_SECTION_BASE = {
    "id": "sec-014",
    "paper_book_id": "pb-001",
    "name": "",
    "order_index": 14,
    "page_number_column": "part1",
    "is_default": False,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

# ---------------------------------------------------------------------------


@sectionsListRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def list_sections(
    request: Request,
    paper_book_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"sections": MOCK_SECTIONS_LIST}, message="Sections retrieved successfully")
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
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    response = {"sections": res.data or []}
    return Success(data=response, message="Sections retrieved successfully")


@sectionsListRouter.post("/", dependencies=[Depends(AuthenticationRequired)])
async def create_section(
    request: Request,
    paper_book_id: str,
    payload: SectionCreate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        **MOCK_SECTION_BASE,
        "paper_book_id": paper_book_id,
        "name": payload.name,
        "order_index": payload.order_index if payload.order_index is not None else MOCK_SECTION_BASE["order_index"],
        "page_number_column": payload.page_number_column.value,
        "is_default": False,
    }
    return Success(data={"section": [mock_created]}, message="Section created successfully")
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

    # Determine order_index: append at end if not provided
    if payload.order_index is not None:
        order_index = payload.order_index
    else:
        res = (
            await supabase.table("paper_book_sections")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        max_order = res.data[0]["order_index"] if res.data else 0
        order_index = max_order + 1

    res = (
        await supabase.table("paper_book_sections")
        .insert({
            "paper_book_id": paper_book_id,
            "name": payload.name,
            "order_index": order_index,
            "page_number_column": payload.page_number_column.value,
            "is_default": False,
        })
        .execute()
    )
    response = {"section": res.data}
    return Success(data=response, message="Section created successfully")


@sectionsListRouter.patch("/reorder/", dependencies=[Depends(AuthenticationRequired)])
async def reorder_sections(
    request: Request,
    paper_book_id: str,
    payload: SectionReorder,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_reordered = [
        {**MOCK_SECTIONS_LIST[idx % len(MOCK_SECTIONS_LIST)], "id": section_id, "order_index": idx + 1}
        for idx, section_id in enumerate(payload.ordered_ids)
    ]
    return Success(data={"updated_sections": mock_reordered}, message="Sections reordered successfully")
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

    updated = []
    for idx, section_id in enumerate(payload.ordered_ids):
        res = (
            await supabase.table("paper_book_sections")
            .update({"order_index": idx + 1})
            .eq("id", section_id)
            .eq("paper_book_id", paper_book_id)
            .execute()
        )
        if res.data:
            updated.append(res.data[0])

    response = {"updated_sections": updated}
    return Success(data=response, message="Sections reordered successfully")
