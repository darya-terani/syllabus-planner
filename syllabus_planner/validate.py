"""Sanity checks on an extracted syllabus.

LLMs make confident mistakes, so the app never trusts output blindly. These
checks catch the common ones and turn them into warnings the student sees
before exporting anything to their calendar.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Optional

from .schema import Syllabus

# Approximate quarter/semester windows (month ranges, inclusive).
TERM_MONTHS = {
    "fall": (8, 12),
    "winter": (1, 3),
    "spring": (3, 6),
    "summer": (6, 9),
}


def year_from_term(term: Optional[str]) -> Optional[int]:
    if not term:
        return None
    m = re.search(r"(20\d{2})", term)
    return int(m.group(1)) if m else None


def term_window(term: Optional[str]) -> Optional[tuple[date, date]]:
    year = year_from_term(term)
    if not term or not year:
        return None
    for season, (start_m, end_m) in TERM_MONTHS.items():
        if season in term.lower():
            end_day = 31 if end_m in (1, 3, 5, 7, 8, 10, 12) else 30
            return date(year, start_m, 1), date(year, end_m, end_day)
    return None


def dedupe(syllabus: Syllabus) -> Syllabus:
    """Drop exact repeats (same date + same normalized title), which happen when a
    syllabus lists an item in both a schedule table and a prose paragraph."""
    seen = set()
    unique = []
    for d in syllabus.deadlines:
        key = (d.due_date, re.sub(r"\W+", "", d.title.lower()))
        if key not in seen:
            seen.add(key)
            unique.append(d)
    return syllabus.model_copy(update={"deadlines": sorted(unique, key=lambda d: d.due_date)})


def check(syllabus: Syllabus, term_hint: Optional[str] = None) -> list[str]:
    warnings: list[str] = []

    if not syllabus.deadlines:
        warnings.append("No dated deadlines were found. The schedule may be on a separate page or in an image.")

    if syllabus.grade_components:
        total = sum(c.weight_pct for c in syllabus.grade_components)
        if abs(total - 100) > 1:
            warnings.append(f"Grade weights add up to {total:g}%, not 100%. Check for missing or extra-credit categories.")

    window = term_window(term_hint or syllabus.term)
    if window:
        start, end = window
        for d in syllabus.deadlines:
            if not (start <= d.due_date <= end):
                warnings.append(f"'{d.title}' is dated {d.due_date}, outside {term_hint or syllabus.term}. Possible wrong year or month.")

    return warnings
