"""Score extracted syllabi against hand-labeled answers.

Matching rules (stated up front so the numbers mean something):
  * A predicted deadline matches a labeled one if the DATE is identical and
    either the titles are similar (fuzzy ratio >= 0.5) or the types agree.
    Each labeled item can be matched at most once.
  * A grade component matches if the names are similar (ratio >= 0.5);
    its weight counts as correct if within 0.5 percentage points.

Metrics:
  * Deadline precision = matched / predicted   (how much of the output is right)
  * Deadline recall    = matched / labeled     (how much of the truth was found)
  * F1 = harmonic mean of the two
  * Grade weight accuracy = correct weights / labeled components
All are micro-averaged: pooled across every syllabus, so a syllabus with 30
deadlines counts more than one with 3.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .schema import Syllabus

TITLE_THRESHOLD = 0.5
WEIGHT_TOLERANCE = 0.5


def _norm(text: str) -> str:
    text = text.lower()
    text = re.sub(r"\bhw\b", "homework", text)
    text = re.sub(r"\bmt\b", "midterm", text)
    return re.sub(r"[^a-z0-9 ]+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


@dataclass
class Score:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    comp_labeled: int = 0
    comp_found: int = 0
    comp_weight_correct: int = 0
    errors: list[str] = field(default_factory=list)

    def add(self, other: "Score") -> None:
        for name in ("tp", "fp", "fn", "comp_labeled", "comp_found", "comp_weight_correct"):
            setattr(self, name, getattr(self, name) + getattr(other, name))
        self.errors += other.errors

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    @property
    def weight_accuracy(self) -> float:
        return self.comp_weight_correct / self.comp_labeled if self.comp_labeled else 0.0


def score_one(pred: Syllabus, gold: Syllabus, name: str = "") -> Score:
    s = Score()
    unmatched_pred = list(pred.deadlines)

    for g in gold.deadlines:
        best, best_sim = None, -1.0
        for p in unmatched_pred:
            if p.due_date != g.due_date:
                continue
            sim = similarity(p.title, g.title)
            if (sim >= TITLE_THRESHOLD or p.type == g.type) and sim > best_sim:
                best, best_sim = p, sim
        if best is not None:
            s.tp += 1
            unmatched_pred.remove(best)
        else:
            s.fn += 1
            s.errors.append(f"[{name}] MISSED: {g.title} ({g.type.value}, {g.due_date})")

    for p in unmatched_pred:
        s.fp += 1
        s.errors.append(f"[{name}] EXTRA:  {p.title} ({p.type.value}, {p.due_date})")

    remaining = list(pred.grade_components)
    for g in gold.grade_components:
        s.comp_labeled += 1
        match = max(remaining, key=lambda c: similarity(c.name, g.name), default=None)
        if match is not None and similarity(match.name, g.name) >= TITLE_THRESHOLD:
            s.comp_found += 1
            remaining.remove(match)
            if abs(match.weight_pct - g.weight_pct) <= WEIGHT_TOLERANCE:
                s.comp_weight_correct += 1
            else:
                s.errors.append(f"[{name}] WRONG WEIGHT: {g.name} predicted {match.weight_pct:g}%, labeled {g.weight_pct:g}%")
        else:
            s.errors.append(f"[{name}] MISSED COMPONENT: {g.name} ({g.weight_pct:g}%)")
    return s


N_BOOTSTRAP = 1000
METRICS = ("precision", "recall", "f1", "weight_accuracy")


def bootstrap_ci(results: dict[str, Score], n: int = N_BOOTSTRAP, alpha: float = 0.05, seed: int = 0) -> dict[str, tuple[float, float]]:
    """Percentile bootstrap confidence intervals for the pooled (micro) metrics.

    The unit we resample is the SYLLABUS, not the individual deadline. Deadlines in
    the same syllabus are not independent: if a syllabus uses an unusual format,
    the extractor tends to miss several of its dates at once. Resampling single
    deadlines would pretend those errors are independent and give intervals that
    are too narrow.

    Steps: draw len(results) syllabi with replacement, pool their counts, compute
    the metric; repeat n times; report the alpha/2 and 1-alpha/2 percentiles.
    """
    import random

    rng = random.Random(seed)  # fixed seed so the report is reproducible
    scores = list(results.values())
    if not scores:
        return {m: (0.0, 0.0) for m in METRICS}

    samples: dict[str, list[float]] = {m: [] for m in METRICS}
    for _ in range(n):
        pooled = Score()
        for s in rng.choices(scores, k=len(scores)):
            pooled.add(Score(s.tp, s.fp, s.fn, s.comp_labeled, s.comp_found, s.comp_weight_correct))
        for m in METRICS:
            samples[m].append(getattr(pooled, m))

    def percentile(values: list[float], q: float) -> float:
        ordered = sorted(values)
        return ordered[min(len(ordered) - 1, max(0, round(q * (len(ordered) - 1))))]

    return {m: (percentile(v, alpha / 2), percentile(v, 1 - alpha / 2)) for m, v in samples.items()}


def report(results: dict[str, Score], method: str) -> str:
    total = Score()
    rows = []
    for name, s in sorted(results.items()):
        total.add(s)
        rows.append(f"| {name} | {s.precision:.2f} | {s.recall:.2f} | {s.f1:.2f} | {s.weight_accuracy:.2f} |")
    ci = bootstrap_ci(results)

    def fmt(metric: str) -> str:
        low, high = ci[metric]
        return f"{getattr(total, metric):.3f} | [{low:.3f}, {high:.3f}]"

    header = [
        f"## Results: {method} ({len(results)} syllabi)",
        "",
        f"| Metric | Value | 95% bootstrap CI ({N_BOOTSTRAP:,} resamples) |",
        "| --- | --- | --- |",
        f"| Deadline precision | {fmt('precision')} |",
        f"| Deadline recall | {fmt('recall')} |",
        f"| Deadline F1 | {fmt('f1')} |",
        f"| Grade weight accuracy | {fmt('weight_accuracy')} |",
        f"| Labeled deadlines | {total.tp + total.fn} | |",
        "",
        "Confidence intervals resample whole syllabi with replacement, because errors "
        "cluster by syllabus (a messy format tends to break many deadlines at once).",
        "",
        "### Per syllabus",
        "",
        "| Syllabus | Precision | Recall | F1 | Weight acc. |",
        "| --- | --- | --- | --- | --- |",
    ]
    errors = ["", "### Errors (for error analysis)", ""] + [f"- {e}" for e in total.errors] if total.errors else []
    return "\n".join(header + rows + errors) + "\n"
