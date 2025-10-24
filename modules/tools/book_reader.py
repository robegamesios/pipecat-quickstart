from __future__ import annotations

from typing import Any, Dict

from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams

from loguru import logger

from modules.books.handlers import (
    focus_document_by_index,
    get_book_overview,
    get_document_list,
    list_sections,
    show_next_section,
    show_previous_section,
    show_section,
    upload_document,
)


async def book_upload_epub(params: FunctionCallParams) -> None:
    args = params.arguments or {}
    path = str(args.get("path", "")).strip()
    ok, msg, info = await upload_document(path)
    await params.result_callback({"success": ok, "message": msg, "document": info})


async def book_list(params: FunctionCallParams) -> None:
    ok, msg, docs = await get_document_list()
    await params.result_callback({"success": ok, "message": msg, "documents": docs or {}})


async def book_focus(params: FunctionCallParams) -> None:
    args = params.arguments or {}
    index = str(args.get("index", "")).strip()
    msg = await focus_document_by_index(index)
    await params.result_callback({"message": msg})


async def book_list_chapters(params: FunctionCallParams) -> None:
    msg = await list_sections()
    await params.result_callback({"message": msg})


async def book_read_chapter(params: FunctionCallParams) -> None:
    args = params.arguments or {}
    n = str(args.get("number", "")).strip()
    msg = await show_section(n)
    await params.result_callback({"message": msg})


async def book_next_chapter(params: FunctionCallParams) -> None:
    msg = await show_next_section()
    await params.result_callback({"message": msg})


async def book_previous_chapter(params: FunctionCallParams) -> None:
    msg = await show_previous_section()
    await params.result_callback({"message": msg})


async def book_overview(params: FunctionCallParams) -> None:
    msg = await get_book_overview()
    await params.result_callback({"message": msg})


def create_book_tools() -> ToolsSchema:
    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name="book_upload_epub",
                description="Upload and process a local EPUB file by path.",
                properties={
                    "path": {
                        "type": "string",
                        "description": "Absolute or relative path to .epub",
                    }
                },
                required=["path"],
            ),
            FunctionSchema(
                name="book_list",
                description="List uploaded books with id/title/author/chapters.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="book_focus",
                description="Focus on a book by 1-based index from book_list.",
                properties={
                    "index": {"type": "string", "description": "1-based index"}
                },
                required=["index"],
            ),
            FunctionSchema(
                name="book_list_chapters",
                description="List chapter numbers and titles for the focused book.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="book_read_chapter",
                description="Read a specific chapter/section by number.",
                properties={"number": {"type": "integer"}},
                required=["number"],
            ),
            FunctionSchema(
                name="book_next_chapter",
                description="Read the next chapter/section in sequence.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="book_previous_chapter",
                description="Read the previous chapter/section in sequence.",
                properties={},
                required=[],
            ),
            FunctionSchema(
                name="book_overview",
                description="Provide an overview by sampling key chapters.",
                properties={},
                required=[],
            ),
        ]
    )


def register_book_tools(llm) -> None:
    llm.register_function("book_upload_epub", book_upload_epub)
    llm.register_function("book_list", book_list)
    llm.register_function("book_focus", book_focus)
    llm.register_function("book_list_chapters", book_list_chapters)
    llm.register_function("book_read_chapter", book_read_chapter)
    llm.register_function("book_next_chapter", book_next_chapter)
    llm.register_function("book_previous_chapter", book_previous_chapter)
    llm.register_function("book_overview", book_overview)
