"""Write deadlines to an .ics file that Google Calendar, Apple Calendar and
Outlook can all import. Written by hand (it's a simple text format) to avoid
an extra dependency.

Items without a time become all-day events. Items with a time use "floating"
local time, so 23:59 means 23:59 wherever the student is.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from .schema import ItemType, Syllabus

REMINDER_DAYS = {ItemType.exam: 3, ItemType.project: 3, ItemType.assignment: 1, ItemType.quiz: 1, ItemType.other: 1}


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold(line: str) -> str:
    """RFC 5545: lines longer than 75 octets are folded onto continuation lines."""
    out, current = [], line
    while len(current.encode()) > 75:
        cut = 75
        while len(current[:cut].encode()) > 75:
            cut -= 1
        out.append(current[:cut])
        current = " " + current[cut:]
    out.append(current)
    return "\r\n".join(out)


def to_ics(syllabus: Syllabus) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"{syllabus.course_code}: " if syllabus.course_code else ""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//syllabus-planner//EN",
        "CALSCALE:GREGORIAN",
    ]
    for d in syllabus.deadlines:
        uid_src = f"{syllabus.course_code}|{d.title}|{d.due_date}"
        uid = hashlib.sha1(uid_src.encode()).hexdigest()[:16] + "@syllabus-planner"
        lines += ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"SUMMARY:{_escape(prefix + d.title)}"]
        if d.due_time:
            hh, mm = d.due_time.split(":")[:2]
            start = datetime(d.due_date.year, d.due_date.month, d.due_date.day, int(hh), int(mm))
            lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{start + timedelta(minutes=30):%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{d.due_date:%Y%m%d}", f"DTEND;VALUE=DATE:{d.due_date + timedelta(days=1):%Y%m%d}"]
        lines.append(f"CATEGORIES:{d.type.value.upper()}")
        if d.source_text:
            lines.append(f"DESCRIPTION:{_escape('From syllabus: ' + d.source_text)}")
        days = REMINDER_DAYS[d.type]
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_escape(d.title)} due in {days} day(s)",
            f"TRIGGER:-P{days}D",
            "END:VALARM",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(_fold(line) for line in lines) + "\r\n"
