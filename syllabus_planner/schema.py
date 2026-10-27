"""Data model for everything we pull out of a syllabus.

The same schema is used for three things:
  1. the JSON schema the LLM must fill in (so its output is structured, not free text)
  2. the hand-labeled "gold" answers used for evaluation
  3. the data the app shows and exports to a calendar
"""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ItemType(str, Enum):
    exam = "exam"            # midterms and finals
    quiz = "quiz"
    assignment = "assignment"  # homework, problem sets, labs, essays
    project = "project"      # projects, papers, presentations
    other = "other"


class Deadline(BaseModel):
    title: str = Field(description="Short name as written in the syllabus, e.g. 'Midterm 1' or 'HW 3'.")
    type: ItemType
    due_date: date = Field(description="Due date in ISO format, YYYY-MM-DD.")
    due_time: Optional[str] = Field(default=None, description="Time of day if stated, 24h 'HH:MM', else null.")
    source_text: Optional[str] = Field(
        default=None,
        description="The exact short phrase from the syllabus this item came from, for auditing.",
    )


class GradeComponent(BaseModel):
    name: str = Field(description="Category name, e.g. 'Homework' or 'Final Exam'.")
    weight_pct: float = Field(ge=0, le=100, description="Percent of the final grade, 0-100.")


class Syllabus(BaseModel):
    course_code: Optional[str] = Field(default=None, description="e.g. 'STA 141B'.")
    course_title: Optional[str] = None
    term: Optional[str] = Field(default=None, description="e.g. 'Fall 2026'.")
    grade_components: list[GradeComponent] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
