"""Command line entry points.

  python -m syllabus_planner extract path/to/syllabus.pdf --term "Fall 2026"
  python -m syllabus_planner eval --method llm
  python -m syllabus_planner eval --method baseline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluate import report, score_one
from .extract_baseline import extract_with_baseline
from .ics import to_ics
from .pdf_text import extract_text
from .schema import Syllabus
from .validate import check, dedupe


def run_extraction(pdf: Path, term: str | None, method: str, model: str | None = None) -> Syllabus:
    text = extract_text(pdf)
    if text.looks_scanned:
        print(f"warning: {pdf.name} looks like a scanned PDF; text extraction may be empty", file=sys.stderr)
    if method == "baseline":
        result = extract_with_baseline(text.text, term)
    else:
        from .extract_llm import DEFAULT_MODEL, extract_with_llm

        result = extract_with_llm(text.text, term, model=model or DEFAULT_MODEL)
    return dedupe(result)


def cmd_extract(args: argparse.Namespace) -> None:
    pdf = Path(args.pdf)
    syllabus = run_extraction(pdf, args.term, args.method, args.model)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{pdf.stem}.json").write_text(json.dumps(syllabus.model_dump(mode="json"), indent=2))
    (out_dir / f"{pdf.stem}.ics").write_text(to_ics(syllabus))
    for w in check(syllabus, args.term):
        print(f"warning: {w}", file=sys.stderr)
    print(f"{len(syllabus.deadlines)} deadlines, {len(syllabus.grade_components)} grade components -> {out_dir}/")


def cmd_eval(args: argparse.Namespace) -> None:
    labels = sorted(Path(args.labels).glob("*.json"))
    if not labels:
        sys.exit(f"No label files found in {args.labels}")
    label_tag = args.model or args.method
    pred_dir = Path(args.results) / label_tag.replace("/", "_")
    pred_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for label_path in labels:
        gold = Syllabus.model_validate_json(label_path.read_text())
        pdf = Path(args.pdfs) / f"{label_path.stem}.pdf"
        if not pdf.exists():
            print(f"skip {label_path.stem}: no matching PDF", file=sys.stderr)
            continue
        cached = pred_dir / f"{label_path.stem}.json"
        if cached.exists() and not args.refresh:
            pred = Syllabus.model_validate_json(cached.read_text())  # avoid paying for the API twice
        else:
            pred = run_extraction(pdf, gold.term, args.method, args.model)
            cached.write_text(json.dumps(pred.model_dump(mode="json"), indent=2))
        results[label_path.stem] = score_one(pred, gold, label_path.stem)
        print(f"{label_path.stem}: F1 {results[label_path.stem].f1:.2f}")

    text = report(results, label_tag)
    out = Path(args.results) / f"report_{label_tag.replace('/', '_')}.md"
    out.write_text(text)
    print(f"\nReport written to {out}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="syllabus_planner")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="Extract one syllabus to JSON + .ics")
    p.add_argument("pdf")
    p.add_argument("--term", help='e.g. "Fall 2026" (used to infer missing years)')
    p.add_argument("--method", choices=["llm", "baseline"], default="llm")
    p.add_argument("--model", help="Override the LLM model")
    p.add_argument("--out", default="output")
    p.set_defaults(func=cmd_extract)

    e = sub.add_parser("eval", help="Score extraction against hand labels")
    e.add_argument("--method", choices=["llm", "baseline"], default="llm")
    e.add_argument("--model", help="Override the LLM model (e.g. to compare models)")
    e.add_argument("--pdfs", default="data/syllabi")
    e.add_argument("--labels", default="data/labels")
    e.add_argument("--results", default="results")
    e.add_argument("--refresh", action="store_true", help="Ignore cached predictions")
    e.set_defaults(func=cmd_eval)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
