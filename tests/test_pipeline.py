from datetime import date
from pathlib import Path
from types import SimpleNamespace

from syllabus_planner.evaluate import score_one
from syllabus_planner.extract_baseline import extract_with_baseline
from syllabus_planner.extract_llm import extract_with_llm
from syllabus_planner.ics import to_ics
from syllabus_planner.pdf_text import extract_text
from syllabus_planner.schema import Deadline, GradeComponent, ItemType, Syllabus
from syllabus_planner.validate import check, dedupe

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def make(deadlines=(), components=(), term="Fall 2026"):
    return Syllabus(
        course_code="DSC 101",
        term=term,
        deadlines=[Deadline(title=t, type=k, due_date=d) for t, k, d in deadlines],
        grade_components=[GradeComponent(name=n, weight_pct=w) for n, w in components],
    )


# ---- evaluation -------------------------------------------------------------

def test_perfect_prediction_scores_one():
    gold = make([("HW 1", ItemType.assignment, date(2026, 10, 2))], [("Homework", 100)])
    s = score_one(gold, gold)
    assert (s.precision, s.recall, s.f1, s.weight_accuracy) == (1, 1, 1, 1)


def test_wrong_date_counts_as_miss_and_extra():
    gold = make([("HW 1", ItemType.assignment, date(2026, 10, 2))])
    pred = make([("HW 1", ItemType.assignment, date(2026, 10, 1))])
    s = score_one(pred, gold)
    assert (s.tp, s.fp, s.fn) == (0, 1, 1)


def test_fuzzy_title_matches():
    gold = make([("Homework 1", ItemType.assignment, date(2026, 10, 2))])
    pred = make([("HW 1", ItemType.other, date(2026, 10, 2))])
    assert score_one(pred, gold).tp == 1


def test_wrong_weight_is_flagged():
    gold = make(components=[("Final Exam", 25)])
    pred = make(components=[("Final exam", 30)])
    s = score_one(pred, gold)
    assert s.weight_accuracy == 0 and any("WRONG WEIGHT" in e for e in s.errors)


# ---- validation -------------------------------------------------------------

def test_weights_not_summing_to_100_warns():
    assert any("add up to 90%" in w for w in check(make(components=[("A", 50), ("B", 40)])))


def test_date_outside_term_warns():
    syl = make([("Final", ItemType.exam, date(2025, 12, 10))])
    assert any("outside" in w for w in check(syl, "Fall 2026"))


def test_dedupe_removes_repeats():
    d = date(2026, 12, 4)
    syl = make([("Final project report", ItemType.project, d), ("Final Project Report", ItemType.project, d)])
    assert len(dedupe(syl).deadlines) == 1


# ---- calendar export -------------------------------------------------------

def test_ics_has_one_event_per_deadline():
    syl = make([("HW 1", ItemType.assignment, date(2026, 10, 2)), ("Midterm", ItemType.exam, date(2026, 10, 22))])
    ics = to_ics(syl)
    assert ics.count("BEGIN:VEVENT") == 2
    assert "DTSTART;VALUE=DATE:20261002" in ics
    assert all(len(line.encode()) <= 75 for line in ics.split("\r\n"))


def test_ics_timed_event():
    syl = Syllabus(deadlines=[Deadline(title="Final", type="exam", due_date=date(2026, 12, 10), due_time="10:30")])
    assert "DTSTART:20261210T103000" in to_ics(syl)


# ---- extractors ------------------------------------------------------------

def test_baseline_on_sample_syllabus():
    gold = Syllabus.model_validate_json((EXAMPLES / "sample_syllabus.json").read_text())
    text = extract_text(EXAMPLES / "sample_syllabus.pdf").text
    pred = dedupe(extract_with_baseline(text, "Fall 2026"))
    assert score_one(pred, gold).recall >= 0.9


class FakeClient:
    """Stands in for the Anthropic client so tests run without an API key."""

    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = 0
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        self.calls += 1
        block = SimpleNamespace(type="tool_use", id=f"tool_{self.calls}", input=self.outputs.pop(0))
        return SimpleNamespace(content=[block])


VALID = {
    "course_code": "DSC 101",
    "grade_components": [{"name": "Homework", "weight_pct": 100}],
    "deadlines": [{"title": "HW 1", "type": "assignment", "due_date": "2026-10-02"}],
}


def test_llm_extractor_parses_tool_output():
    client = FakeClient([VALID])
    result = extract_with_llm("syllabus text", "Fall 2026", client=client)
    assert result.deadlines[0].due_date == date(2026, 10, 2) and client.calls == 1


def test_llm_extractor_retries_once_on_invalid_output():
    bad = {**VALID, "deadlines": [{"title": "HW 1", "type": "assignment", "due_date": "Oct 2"}]}
    client = FakeClient([bad, VALID])
    result = extract_with_llm("syllabus text", "Fall 2026", client=client)
    assert client.calls == 2 and len(result.deadlines) == 1
