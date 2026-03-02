from pydantic import BaseModel, Field
from typing import Optional, List


class BookmarkCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    page_number: int = Field(..., ge=1)
    index_row_id: Optional[str] = None
    order_index: Optional[int] = None


class BookmarkUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    page_number: Optional[int] = Field(None, ge=1)


class BookmarkReorder(BaseModel):
    ordered_ids: List[str] = Field(..., description="Bookmark IDs in desired order")
