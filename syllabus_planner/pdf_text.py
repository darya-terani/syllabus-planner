"""Turn a syllabus PDF into plain text.

pdfplumber keeps table rows on one line, which matters because many syllabi
put their schedule in a table. If a page has almost no text it is probably a
scanned image; we flag that rather than silently returning nothing.
"""

from __future__ import annotations

from pathlib import Path

import pdfplumber

MIN_CHARS_PER_PAGE = 50  # below this, the page is probably a scanned image


class ExtractedText:
    def __init__(self, text: str, n_pages: int, likely_scanned_pages: list[int]):
        self.text = text
        self.n_pages = n_pages
        self.likely_scanned_pages = likely_scanned_pages

    @property
    def looks_scanned(self) -> bool:
        return self.n_pages > 0 and len(self.likely_scanned_pages) == self.n_pages


def extract_text(pdf_path: str | Path) -> ExtractedText:
    pages_text: list[str] = []
    scanned: list[int] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if len(text.strip()) < MIN_CHARS_PER_PAGE:
                scanned.append(i)
            pages_text.append(f"--- Page {i} ---\n{text}")
        n_pages = len(pdf.pages)
    return ExtractedText("\n\n".join(pages_text), n_pages, scanned)
