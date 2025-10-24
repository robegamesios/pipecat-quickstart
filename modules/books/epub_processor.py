from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List

import ebooklib
from bs4 import BeautifulSoup
from ebooklib import epub


@dataclass
class DocumentChunk:
    id: str
    document_id: str
    title: str
    content: str
    chapter: str
    chunk_index: int
    metadata: Dict[str, Any]


@dataclass
class EPUBDocument:
    id: str
    title: str
    author: str
    chapters: List[Dict[str, str]]
    chunks: List[DocumentChunk]
    metadata: Dict[str, Any]


class EPUBProcessor:
    """Parse EPUB files, extract chapters, and create overlapping chunks."""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def process_epub(self, file_path: str) -> EPUBDocument:
        doc_id = str(uuid.uuid4())

        book = epub.read_epub(file_path)

        title = (
            book.get_metadata("DC", "title")[0][0]
            if book.get_metadata("DC", "title")
            else "Unknown Title"
        )
        author = (
            book.get_metadata("DC", "creator")[0][0]
            if book.get_metadata("DC", "creator")
            else "Unknown Author"
        )

        chapters: List[Dict[str, str]] = []
        all_chunks: List[DocumentChunk] = []

        for item in book.get_items():
            if item.get_type() != ebooklib.ITEM_DOCUMENT:
                continue
            soup = BeautifulSoup(item.get_content(), "html.parser")
            text_content = soup.get_text()
            cleaned = self._clean_text(text_content)
            if not cleaned.strip() or len(cleaned.split()) <= 50:
                continue

            ch_title = self._extract_chapter_title(
                soup, item.get_name(), len(chapters) + 1
            )
            chapters.append({"title": ch_title, "content": cleaned})

            ch_chunks = self._create_chunks(
                doc_id=doc_id,
                chapter_title=ch_title,
                content=cleaned,
                chapter_index=len(chapters),
            )
            all_chunks.extend(ch_chunks)

        metadata = {
            "file_path": file_path,
            "total_chapters": len(chapters),
            "total_chunks": len(all_chunks),
            "language": (
                book.get_metadata("DC", "language")[0][0]
                if book.get_metadata("DC", "language")
                else "en"
            ),
        }

        return EPUBDocument(
            id=doc_id,
            title=title,
            author=author,
            chapters=chapters,
            chunks=all_chunks,
            metadata=metadata,
        )

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        # Keep common punctuation and word chars
        text = re.sub(r"[^\w\s\.,!?;:'\"()\-]", "", text)
        return text

    def _extract_chapter_title(
        self, soup: BeautifulSoup, filename: str, chapter_num: int
    ) -> str:
        selectors = [
            "h1",
            "h2",
            "h3",
            ".chapter-title",
            ".title",
            '[class*="title"]',
            '[class*="chapter"]',
        ]
        for sel in selectors:
            els = soup.select(sel)
            for el in els:
                t = (el.get_text() or "").strip()
                if t and len(t) < 100 and not t.lower().startswith("copyright"):
                    t = re.sub(r"\s+", " ", t).strip()
                    if t:
                        return t

        text_content = (soup.get_text() or "").strip()
        if text_content:
            lines = text_content.split("\n")[:5]
            for ln in lines:
                s = ln.strip()
                if s and len(s.split()) <= 10 and len(s) < 100:
                    if not any(x in s.lower() for x in ["copyright", "page", "isbn", "published"]):
                        return s

        if filename and re.search(r"ch\d+", filename.lower()):
            m = re.search(r"ch(\d+)", filename.lower())
            if m:
                return f"Chapter {int(m.group(1))}"

        if filename:
            nm = filename.replace(".html", "").replace(".xhtml", "")
            nm = re.sub(r"^Text/", "", nm)
            nm = re.sub(r"\d+_", "", nm)
            nm = re.sub(r"_ch(\d+)", r" Chapter \1", nm)
            nm = nm.replace("_", " ").title()
            if nm and nm != filename:
                return nm

        return f"Chapter {chapter_num}"

    def _create_chunks(
        self, *, doc_id: str, chapter_title: str, content: str, chapter_index: int
    ) -> List[DocumentChunk]:
        words = content.split()
        if not words:
            return []

        chunk_word_size = self.chunk_size // 5
        overlap_word_size = self.chunk_overlap // 5

        start = 0
        idx = 0
        out: List[DocumentChunk] = []
        while start < len(words):
            end = min(start + chunk_word_size, len(words))
            ch_words = words[start:end]
            chunk_text = " ".join(ch_words)

            out.append(
                DocumentChunk(
                    id=f"{doc_id}_chunk_{idx}",
                    document_id=doc_id,
                    title=f"{chapter_title} (Part {idx + 1})",
                    content=chunk_text,
                    chapter=chapter_title,
                    chunk_index=idx,
                    metadata={
                        "chapter_index": chapter_index,
                        "word_count": len(ch_words),
                        "start_word": start,
                        "end_word": end,
                    },
                )
            )

            if end >= len(words):
                break
            start = end - overlap_word_size
            idx += 1

        return out

