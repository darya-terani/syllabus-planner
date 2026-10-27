"""Rule-based baseline: regular expressions, no machine learning.

Why it exists: an ML result means little without something to compare it to.
The evaluation reports this baseline next to the LLM so the README can say how
much the LLM actually adds, and where simple rules are already good enough.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .schema import Deadline, GradeComponent, ItemType, Syllabus
from .validate import year_from_term

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}

# "Oct 14", "October 14th", "Oct. 14, 2026"
NAMED_DATE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sept?|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?",
    re.IGNORECASE,
)
# "10/14" or "10/14/2026" or "10/14/26"
NUMERIC_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
PERCENT_LINE = re.compile(r"^\s*([A-Za-z][A-Za-z &/\-()]+?)[\s.:\-–]*?(\d{1,3}(?:\.\d+)?)\s*%")

TYPE_KEYWORDS = [
    (ItemType.exam, ("final exam", "midterm", "exam", "final")),
    (ItemType.quiz, ("quiz",)),
    (ItemType.project, ("project", "paper", "presentation", "essay", "report")),
    (ItemType.assignment, ("homework", "hw", "problem set", "pset", "assignment", "lab", "due")),
]


def _classify(line: str) -> Optional[ItemType]:
    lower = line.lower()
    for item_type, words in TYPE_KEYWORDS:
        if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in words):
            return item_type
    return None


def _find_date(line: str, default_year: int) -> Optional[date]:
    """Return the LAST date on the line. In schedule tables the first date is
    usually the lecture date and the due date comes after it ("10/1 ... HW 1 due 10/2")."""
    named = list(NAMED_DATE.finditer(line))
    numeric = list(NUMERIC_DATE.finditer(line))
    candidates = sorted(named + numeric, key=lambda m: m.start())
    if not candidates:
        return None
    m = candidates[-1]
    if m.re is NAMED_DATE:
        month = MONTHS[m.group(1).lower()[:3]]
        year = int(m.group(3)) if m.group(3) else default_year
        try:
            return date(year, month, int(m.group(2)))
        except ValueError:
            return None
    month, day = int(m.group(1)), int(m.group(2))
    year = default_year
    if m.group(3):
        year = int(m.group(3))
        year = year + 2000 if year < 100 else year
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _title_from_line(line: str, item_type: ItemType) -> str:
    cleaned = NAMED_DATE.sub("", line)
    cleaned = NUMERIC_DATE.sub("", cleaned)
    cleaned = re.sub(r"\b(mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)[a-z]*\b\.?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[|:\-–,]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:60] or item_type.value.title()


def extract_with_baseline(text: str, term_hint: Optional[str] = None) -> Syllabus:
    default_year = year_from_term(term_hint) or date.today().year
    deadlines: list[Deadline] = []
    components: list[GradeComponent] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        pct = PERCENT_LINE.match(line)
        if pct and not _find_date(line, default_year):
            weight = float(pct.group(2))
            if 0 < weight <= 100:
                components.append(GradeComponent(name=pct.group(1).strip(), weight_pct=weight))
            continue

        item_type = _classify(line)
        due = _find_date(line, default_year)
        if item_type and due:
            deadlines.append(
                Deadline(title=_title_from_line(line, item_type), type=item_type, due_date=due, source_text=line[:120])
            )

    return Syllabus(term=term_hint, grade_components=components, deadlines=deadlines)
