from fastapi import APIRouter, Depends, Request
from app.schemas.requests import (
    BookmarkCreate, BookmarkUpdate, BookmarkReorder
)
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound


bookmarksRouter = APIRouter()

# ---------------------------------------------------------------------------
# MOCK DATA
# ---------------------------------------------------------------------------

MOCK_BOOKMARK = {
    "id": "bm-001",
    "paper_book_id": "pb-001",
    "index_row_id": "ir-001",
    "title": "0/R on Limitation",
    "page_number": 1,
    "order_index": 1,
    "is_custom": False,
    "created_at": "2025-01-01T00:00:00+00:00",
    "updated_at": "2025-01-01T00:00:00+00:00",
}

MOCK_BOOKMARKS_LIST = [
    {
        "id": "bm-001",
        "paper_book_id": "pb-001",
        "index_row_id": "ir-001",
        "title": "0/R on Limitation",
        "page_number": 1,
        "order_index": 1,
        "is_custom": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "bm-002",
        "paper_book_id": "pb-001",
        "index_row_id": "ir-002",
        "title": "Listing Performa",
        "page_number": 3,
        "order_index": 2,
        "is_custom": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "bm-003",
        "paper_book_id": "pb-001",
        "index_row_id": "ir-003",
        "title": "Cover page of the paper book",
        "page_number": 5,
        "order_index": 3,
        "is_custom": False,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
    {
        "id": "bm-004",
        "paper_book_id": "pb-001",
        "index_row_id": None,
        "title": "Custom Section",
        "page_number": 10,
        "order_index": 4,
        "is_custom": True,
        "created_at": "2025-01-01T00:00:00+00:00",
        "updated_at": "2025-01-01T00:00:00+00:00",
    },
]

MOCK_REORDERED_BOOKMARKS = [
    {**bm, "order_index": idx + 1}
    for idx, bm in enumerate(MOCK_BOOKMARKS_LIST)
]

# ---------------------------------------------------------------------------


@bookmarksRouter.post("/generate/", dependencies=[Depends(AuthenticationRequired)])
async def generate_bookmarks(
    request: Request,
    paper_book_id: str,
):
    """
    Auto-generate bookmarks from existing index rows.
    Deletes existing non-custom bookmarks and regenerates.
    Custom bookmarks are preserved.
    Page number = page_start_part1 (fallback to page_start_part2) from index row.
    """
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"bookmarks": MOCK_BOOKMARKS_LIST}, message="Bookmarks generated successfully")
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

    # Fetch index rows ordered
    rows_res = (
        await supabase.table("paper_book_index_rows")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )
    index_rows = rows_res.data or []

    # Delete existing non-custom bookmarks
    # await supabase.table("paper_book_bookmarks").delete().eq(
    #     "paper_book_id", paper_book_id
    # ).eq("is_custom", False).execute()

    if not index_rows:
        return Success(data={"bookmarks": []}, message="No index rows found, no bookmarks generated")

    bookmarks_to_insert = []
    for idx, row in enumerate(index_rows):
        # Determine page number: prefer part1 start, fallback to part2 start
        page_number = row.get("page_start_part1") or row.get("page_start_part2")
        if page_number is None:
            page_number = 1  # default if no page info yet

        bookmarks_to_insert.append({
            "paper_book_id": paper_book_id,
            "index_row_id": row["id"],
            "title": row["particulars"],
            "page_number": page_number,
            "order_index": idx + 1,
            "is_custom": False,
        })

    res = await supabase.table("paper_book_bookmarks").insert(bookmarks_to_insert).execute()

    # Update paper book status
    await supabase.table("paper_books").update({"status": "bookmarked"}).eq(
        "id", paper_book_id
    ).execute()

    response = {"bookmarks": res.data or []}
    return Success(data=response, message="Bookmarks generated successfully")


@bookmarksRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def list_bookmarks(
    request: Request,
    paper_book_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={"bookmarks": MOCK_BOOKMARKS_LIST}, message="Bookmarks retrieved successfully")
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
        await supabase.table("paper_book_bookmarks")
        .select("*")
        .eq("paper_book_id", paper_book_id)
        .order("order_index")
        .execute()
    )

    response = {"bookmarks": res.data or []}
    return Success(data=response, message="Bookmarks retrieved successfully")


@bookmarksRouter.post("/", dependencies=[Depends(AuthenticationRequired)])
async def create_bookmark(
    request: Request,
    paper_book_id: str,
    payload: BookmarkCreate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_created = {
        **MOCK_BOOKMARK,
        "title": payload.title,
        "page_number": payload.page_number,
        "index_row_id": payload.index_row_id,
        "order_index": payload.order_index if payload.order_index is not None else MOCK_BOOKMARK["order_index"],
        "is_custom": True,
    }
    return Success(data={"bookmark": [mock_created]}, message="Bookmark created successfully")
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
            await supabase.table("paper_book_bookmarks")
            .select("order_index")
            .eq("paper_book_id", paper_book_id)
            .order("order_index", desc=True)
            .limit(1)
            .execute()
        )
        max_order = res.data[0]["order_index"] if res.data else 0
        order_index = max_order + 1

    res = await supabase.table("paper_book_bookmarks").insert({
        "paper_book_id": paper_book_id,
        "index_row_id": payload.index_row_id,
        "title": payload.title,
        "page_number": payload.page_number,
        "order_index": order_index,
        "is_custom": True,
    }).execute()

    response = {"bookmark": res.data}
    return Success(data=response, message="Bookmark created successfully")


@bookmarksRouter.patch("/{bookmark_id}/", dependencies=[Depends(AuthenticationRequired)])
async def update_bookmark(
    request: Request,
    paper_book_id: str,
    bookmark_id: str,
    payload: BookmarkUpdate,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    update_fields = payload.model_dump(exclude_none=True)
    mock_updated = {**MOCK_BOOKMARK, "id": bookmark_id, **update_fields}
    return Success(data={"bookmark": [mock_updated]}, message="Bookmark updated successfully")
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
        await supabase.table("paper_book_bookmarks")
        .select("*")
        .eq("id", bookmark_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Bookmark not found")

    update_data = payload.model_dump(exclude_none=True)

    res = (
        await supabase.table("paper_book_bookmarks")
        .update(update_data)
        .eq("id", bookmark_id)
        .eq("paper_book_id", paper_book_id)
        .execute()
    )

    response = {"bookmark": res.data}
    return Success(data=response, message="Bookmark updated successfully")


@bookmarksRouter.delete("/{bookmark_id}/", dependencies=[Depends(AuthenticationRequired)])
async def delete_bookmark(
    request: Request,
    paper_book_id: str,
    bookmark_id: str,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    return Success(data={}, message="Bookmark deleted successfully")
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
        await supabase.table("paper_book_bookmarks")
        .select("*")
        .eq("id", bookmark_id)
        .eq("paper_book_id", paper_book_id)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Bookmark not found")

    await supabase.table("paper_book_bookmarks").delete().eq("id", bookmark_id).execute()

    response = {}
    return Success(data=response, message="Bookmark deleted successfully")


@bookmarksRouter.patch("/reorder/", dependencies=[Depends(AuthenticationRequired)])
async def reorder_bookmarks(
    request: Request,
    paper_book_id: str,
    payload: BookmarkReorder,
):
    # ── MOCK ────────────────────────────────────────────────────────────────
    mock_reordered = [
        {**MOCK_BOOKMARKS_LIST[idx % len(MOCK_BOOKMARKS_LIST)], "id": bookmark_id, "order_index": idx + 1}
        for idx, bookmark_id in enumerate(payload.ordered_ids)
    ]
    return Success(data={"bookmarks": mock_reordered}, message="Bookmarks reordered successfully")
    # ── END MOCK ─────────────────────────────────────────────────────────────

    supabase = await get_supabase_client(request.state.token)
    res = (
        supabase.table("paper_books")
        .select("id")
        .eq("id", paper_book_id)
        .eq("user_id", request.state.sub)
        .single()
        .execute()
    )
    if not res.data:
        raise NotFound(message="Paper book not found")

    updated = []
    for idx, bookmark_id in enumerate(payload.ordered_ids):
        res = (
            supabase.table("paper_book_bookmarks")
            .update({"order_index": idx + 1})
            .eq("id", bookmark_id)
            .eq("paper_book_id", paper_book_id)
            .execute()
        )
        if res.data:
            updated.append(res.data[0])

    response = {"bookmarks": updated}
    return Success(data=response, message="Bookmarks reordered successfully")
