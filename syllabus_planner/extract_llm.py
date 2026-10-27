"""LLM extractor: syllabus text in, a validated Syllabus object out.

How it works:
  * We give Claude a single "tool" whose input schema is our Syllabus schema and
    force it to call that tool. That makes the model return JSON matching the
    schema instead of prose.
  * Pydantic then validates the JSON. If validation fails (a bad date, a weight
    over 100), we send the error back once and ask the model to fix it.

Set ANTHROPIC_API_KEY in your environment. The model can be changed with the
SYLLABUS_MODEL environment variable, which makes it easy to compare models in
the evaluation.
"""

from __future__ import annotations

import json
import os
from typing import Optional

from pydantic import ValidationError

from .schema import Syllabus

DEFAULT_MODEL = os.environ.get("SYLLABUS_MODEL", "claude-sonnet-5-5")
MAX_TEXT_CHARS = 60_000  # long syllabi are trimmed; ~15 pages of text

SYSTEM_PROMPT = """You extract structured data from university course syllabi.

Rules:
- Only include items that are actually stated in the syllabus. Never invent dates.
- deadlines: every dated exam, quiz, assignment, project, paper or presentation.
  Skip lectures, holidays, office hours and readings with no submission.
- If an item recurs weekly (e.g. "quizzes every Friday") and the syllabus does not
  list the individual dates, do not expand it into separate dates.
- Dates must be YYYY-MM-DD. Syllabi often omit the year: use the term hint to infer it.
- grade_components: the grading breakdown as percentages. Convert points to
  percentages if the syllabus gives points.
- source_text: copy the short phrase you used, so a human can check it.
"""


def _tool_definition() -> dict:
    return {
        "name": "record_syllabus",
        "description": "Record the structured contents of the syllabus.",
        "input_schema": Syllabus.model_json_schema(),
    }


def _build_user_message(text: str, term_hint: Optional[str]) -> str:
    hint = f"Term hint: {term_hint}\n\n" if term_hint else ""
    return f"{hint}Syllabus text:\n<syllabus>\n{text[:MAX_TEXT_CHARS]}\n</syllabus>"


def extract_with_llm(
    text: str,
    term_hint: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    client=None,
) -> Syllabus:
    """Extract a Syllabus from raw text. `client` can be injected for testing."""
    if client is None:
        import anthropic

        client = anthropic.Anthropic()

    messages = [{"role": "user", "content": _build_user_message(text, term_hint)}]

    for attempt in range(2):  # one retry if validation fails
        response = client.messages.create(
            model=model,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=[_tool_definition()],
            tool_choice={"type": "tool", "name": "record_syllabus"},
            messages=messages,
        )
        tool_use = next(block for block in response.content if block.type == "tool_use")
        try:
            return Syllabus.model_validate(tool_use.input)
        except ValidationError as err:
            if attempt == 1:
                raise
            messages += [
                {"role": "assistant", "content": response.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "is_error": True,
                            "content": f"Validation failed, please fix and call the tool again:\n{err}",
                        }
                    ],
                },
            ]
    raise RuntimeError("unreachable")


def to_json(syllabus: Syllabus) -> str:
    return json.dumps(syllabus.model_dump(mode="json"), indent=2)
