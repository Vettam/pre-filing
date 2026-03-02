from fastapi import APIRouter
from .bookmarks.bookmarks import bookmarksRouter
from .paperBooks.paperBook import paperBooksRouter
from .paperBooks.paperBooksList import paperBooksListRouter
from .sections.sections import sectionsRouter
from .sections.sectionsList import sectionsListRouter
from .documents.documentsList import router as documentsListRouter
from .indexRows.indexRows import indexRowsRouter


v1_router = APIRouter(prefix="/v1")
v1_router.include_router(paperBooksListRouter, prefix="/paper-books", tags=["Paper Book"])
v1_router.include_router(paperBooksRouter, prefix="/paper-books/{paper_book_id}", tags=["Paper Book"])
v1_router.include_router(sectionsListRouter, prefix="/paper-books/{paper_book_id}/sections", tags=["Sections"])
v1_router.include_router(sectionsRouter, prefix="/paper-books/{paper_book_id}/sections/{section_id}", tags=["Sections"])
v1_router.include_router(documentsListRouter, prefix="/paper-books/{paper_book_id}/documents", tags=["Documents"])
v1_router.include_router(indexRowsRouter, prefix="/paper-books/{paper_book_id}/index-rows", tags=["Index Rows"])
v1_router.include_router(bookmarksRouter, prefix="/paper-books/{paper_book_id}/bookmarks", tags=["Bookmarks"])
