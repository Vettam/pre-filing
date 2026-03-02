from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, List


class PageNumberColumn(str, Enum):
    part1 = "part1"
    part2 = "part2"
    both = "both"


class SectionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    page_number_column: PageNumberColumn = PageNumberColumn.part1
    order_index: Optional[int] = None  # if None, append at end


class SectionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    page_number_column: Optional[PageNumberColumn] = None


class SectionReorder(BaseModel):
    ordered_ids: List[str] = Field(..., description="Section IDs in desired order")
