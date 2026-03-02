from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class PaperBookStatus(str, Enum):
    draft = "draft"
    documents_uploaded = "documents_uploaded"
    index_created = "index_created"
    bookmarked = "bookmarked"
    completed = "completed"


class PaperBookCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    forum: str = Field(..., min_length=1, max_length=255)
    application_type: str = Field(..., min_length=1, max_length=255)
    client_name: Optional[str] = Field(None, max_length=255)


class PaperBookUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    forum: Optional[str] = Field(None, min_length=1, max_length=255)
    application_type: Optional[str] = Field(None, min_length=1, max_length=255)
    client_name: Optional[str] = None
    status: Optional[PaperBookStatus] = None
