from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from .chroma_store import get_store
from .epub_processor import EPUBProcessor


async def upload_document(file_path: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    if not file_path:
        return False, "File path cannot be empty", None
    if not file_path.lower().endswith(".epub"):
        return False, "Only EPUB files are supported", None

    path = Path(file_path)
    if not path.exists():
        return False, f"File not found: {file_path}", None

    try:
        processor = EPUBProcessor()
        doc = processor.process_epub(str(path))

        store = get_store()
        await store.store_document(doc)

        info = {
            "id": doc.id,
            "title": doc.title,
            "author": doc.author,
            "chapters": len(doc.chapters),
            "chunks": len(doc.chunks),
        }
        return True, f"Processed '{doc.title}'", info
    except Exception as e:
        logger.exception("EPUB processing failed")
        return False, f"Error processing EPUB: {e}", None


async def upload_document_file(
    file_contents: bytes, filename: str
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    try:
        if not filename.lower().endswith(".epub"):
            return False, "Only EPUB files are supported", None

        uploads_dir = Path("./uploads")
        uploads_dir.mkdir(exist_ok=True)
        path = uploads_dir / filename
        with open(path, "wb") as f:
            f.write(file_contents)

        ok, msg, info = await upload_document(str(path))
        try:
            path.unlink(missing_ok=True)
        except Exception:
            pass
        return ok, msg, info
    except Exception as e:
        return False, f"Error processing uploaded file: {e}", None


async def get_document_list() -> Tuple[bool, str, Optional[Dict[str, Dict[str, Any]]]]:
    try:
        store = get_store()
        docs = await store.list_documents()
        if docs:
            return True, f"Found {len(docs)} documents", docs
        return True, "No documents uploaded yet", {}
    except Exception as e:
        return False, f"Error listing documents: {e}", None


async def focus_document_by_index(index_str: str) -> str:
    store = get_store()
    docs = await store.list_documents()
    if not docs:
        return "No documents available. Upload a book first."
    try:
        idx = int(index_str)
    except ValueError:
        return "Invalid index. Use a number like 1."

    keys = list(docs.keys())
    if idx < 1 or idx > len(keys):
        return f"Book {idx} not found. Available: 1-{len(keys)}"

    doc_id = keys[idx - 1]
    store.focus_document(doc_id)
    info = docs[doc_id]
    return (
        f"Focused on book {idx}: '{info.get('title')}' by {info.get('author')} "
        f"({info.get('chapters')} chapters)"
    )


async def list_sections() -> str:
    store = get_store()
    if not store.state.current_document_id:
        return "No document focused. Use focus_book to select one."
    sections = await store.get_chapters(store.state.current_document_id)
    if not sections:
        return "No sections found for the current document."
    lines = ["Sections:"]
    for s in sections:
        lines.append(f"  {s['number']}. {s['title']}")
    return "\n".join(lines)


async def _show_section(n: int) -> str:
    store = get_store()
    if not store.state.current_document_id:
        return "No document focused. Use focus_book to select one."
    content = await store.get_chapter_content(store.state.current_document_id, n)
    if not content:
        return f"Section {n} content not found."
    sections = await store.get_chapters(store.state.current_document_id)
    title = sections[n - 1]["title"] if 0 < n <= len(sections) else f"Section {n}"
    store.set_last_shown_chapter(n)
    return f"{title}\n{'='*60}\n{content}"


async def show_section(n_str: str) -> str:
    try:
        n = int(n_str)
    except ValueError:
        return "Usage: read_chapter(number) expects an integer."
    return await _show_section(n)


async def show_next_section() -> str:
    store = get_store()
    if not store.state.current_document_id:
        return "No document focused. Use focus_book to select one."
    sections = await store.get_chapters(store.state.current_document_id)
    if not sections:
        return "No sections found."
    next_n = (store.state.last_shown_chapter or 0) + 1
    if next_n > len(sections):
        return "Already at the last section."
    return await _show_section(next_n)


async def show_previous_section() -> str:
    store = get_store()
    if not store.state.current_document_id:
        return "No document focused. Use focus_book to select one."
    sections = await store.get_chapters(store.state.current_document_id)
    if not sections:
        return "No sections found."
    prev_n = (store.state.last_shown_chapter or 2) - 1
    if prev_n < 1:
        return "Already at the first section."
    return await _show_section(prev_n)


async def get_book_overview() -> str:
    store = get_store()
    if not store.state.current_document_id:
        return "No document focused. Use focus_book to select one."
    docs = await store.list_documents()
    doc_id = store.state.current_document_id
    info = docs.get(doc_id) or {}
    chs = await store.get_chapters(doc_id)
    if not chs:
        return "No sections found."
    # First 2, middle, last
    indices = []
    if len(chs) >= 1:
        indices.append(1)
    if len(chs) >= 2:
        indices.append(2)
    if len(chs) > 4:
        indices.append(len(chs) // 2)
    if len(chs) > 2:
        indices.append(len(chs))

    parts = []
    for n in indices:
        content = await store.get_chapter_content(doc_id, n)
        preview = content[:500] + ("..." if len(content) > 500 else "")
        parts.append(f"Chapter {n}: {chs[n-1]['title']}\n{preview}")
    header = f"Book Overview for '{info.get('title')}' by {info.get('author')} ({len(chs)} chapters):\n\n"
    return header + "\n\n---\n\n".join(parts)

