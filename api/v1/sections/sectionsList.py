from fastapi import APIRouter, Depends, Request
from typing import List
from app.schemas.requests import SectionCreate, SectionReorder
from core.dependencies import AuthenticationRequired
from core.supabase.client import get_supabase_client
from core.responseTypes import Success, NotFound

sectionsListRouter = APIRouter()


@sectionsListRouter.get("/", dependencies=[Depends(AuthenticationRequired)])
async def list_sections(
    request: Request,
    paper_book_id: str,
):
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
        .select("*, paper_book_documents(id, doc_id, paper_book_files(*))")
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

    # Determine order_index
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

    # If inserting in the middle, shift all existing sections
    # with order_index >= new order_index up by 1
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

    # Insert the new section at the desired order_index
    res = (
        await supabase.table("paper_book_sections")
        .insert({
            "paper_book_id": paper_book_id,
            "name": payload.name,
            "order_index": order_index,
            "page_number_column": payload.page_number_column.value,
            "page_label_style": payload.page_label_style if hasattr(payload, "page_label_style") else None,
            "page_label_prefix": payload.page_label_prefix if hasattr(payload, "page_label_prefix") else None,
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
