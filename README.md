# Syllabus → Semester Planner

Upload a course syllabus PDF and get every deadline, exam and grade weight as structured data, reviewed by you, then exported straight into Google Calendar, Apple Calendar or Outlook.

Every term, students copy dozens of dates out of syllabi by hand, and a missed one costs points. This tool uses an LLM with schema-constrained output to do the extraction, validation checks to catch its mistakes, and a review screen so nothing reaches your calendar unchecked.

> **Status:** v0.1. Evaluation on real syllabi is in progress; results below will be filled in from `results/`.

## Results

Evaluated on **N** hand-labeled syllabi (UC Davis and public course pages) against a rule-based baseline.

| Extractor | Deadline precision | Deadline recall | Deadline F1 (95% CI) | Grade weight accuracy |
| --- | --- | --- | --- | --- |
| Rules (regex baseline) | – | – | – | – |
| Claude (structured output) | – | – | – | – |

Intervals are 95% percentile bootstrap CIs from 1,000 resamples of whole syllabi.

**What the errors show:** _fill in after running the eval, e.g. which formats fail (scanned PDFs, weekly recurring items, dates without a year)._

## How it works

```
PDF ──► text extraction ──► extractor ──► validation ──► review UI ──► .ics calendar
        (pdfplumber,         (LLM or       (weights sum     (edit any
         flags scanned        regex          to 100? dates    row before
         pages)               baseline)      inside term?)    export)
```

1. **Text extraction** (`pdf_text.py`): pulls text page by page and flags pages that look scanned, rather than silently returning nothing.
2. **LLM extraction** (`extract_llm.py`): Claude is given one tool whose input schema *is* the data model, and is forced to call it, so the output is always JSON in the right shape. Pydantic validates it; on a validation error the model gets one chance to fix its output.
3. **Baseline** (`extract_baseline.py`): regex dates plus keyword rules, no ML. It exists so the LLM's numbers mean something.
4. **Validation** (`validate.py`): warns when grade weights don't sum to 100%, when a date falls outside the term (usually a wrong year), and removes duplicates.
5. **Calendar export** (`ics.py`): standard iCalendar with reminders (3 days before exams and projects, 1 day before assignments).
6. **Evaluation** (`evaluate.py`): precision, recall and F1 on deadlines, plus grade weight accuracy, with an error list for analysis.

### Evaluation method

- A predicted deadline counts as correct only if the **date is exact** and the title is similar (fuzzy ratio ≥ 0.5) or the item type matches. Each labeled item can be matched once.
- A grade weight is correct if within 0.5 percentage points.
- Metrics are micro-averaged across all syllabi.
- Uncertainty: with a few dozen syllabi, a single F1 number can mislead, so each metric gets a 95% bootstrap confidence interval. The resampling unit is the syllabus, not the deadline, because errors cluster within a syllabus (one unusual format can break many dates at once), and resampling deadlines independently would make the intervals too narrow.
- The term (e.g. "Fall 2026") is passed to both extractors, since a student selects it in the app.

## Quickstart

```bash
pip install -r requirements.txt

# Try it with no API key (rule-based extractor) on the included fictional syllabus
python -m syllabus_planner extract examples/sample_syllabus.pdf --term "Fall 2026" --method baseline

# Use the LLM extractor
export ANTHROPIC_API_KEY=your-key
python -m syllabus_planner extract examples/sample_syllabus.pdf --term "Fall 2026"

# Web app
streamlit run app.py

# Tests
pytest
```

## Running the evaluation

1. Put syllabus PDFs in `data/syllabi/` (this folder is git-ignored: syllabi belong to their instructors).
2. For each one, write the correct answers to `data/labels/<same-name>.json`, following `examples/sample_syllabus.json`.
3. Run both extractors:

```bash
python -m syllabus_planner eval --method baseline
python -m syllabus_planner eval --method llm
python -m syllabus_planner eval --method llm --model claude-haiku-5-5   # compare a cheaper model
```

Reports land in `results/`. Predictions are cached, so re-running doesn't call the API again unless you pass `--refresh`.

## Project structure

```
syllabus_planner/
  schema.py            data model shared by the LLM, the labels and the app
  pdf_text.py          PDF → text, scanned-page detection
  extract_llm.py       Claude structured extraction with validation retry
  extract_baseline.py  regex + keyword baseline
  validate.py          sanity checks and de-duplication
  ics.py               calendar export
  evaluate.py          metrics and error analysis
  cli.py               extract / eval commands
app.py                 Streamlit web app
examples/              fictional sample syllabus + its label
scripts/               generator for the sample syllabus
tests/                 unit tests (LLM is mocked; no API key needed)
```

## Known limitations

- Scanned (image-only) PDFs are detected but not read; OCR is a planned addition.
- Recurring items with no listed dates ("quizzes every Friday") are intentionally not expanded into dates, since guessing would put wrong dates on a calendar.
- Term windows are approximate quarter/semester ranges and may flag legitimate early or late dates.

## Author

Darya Terani, B.S. Statistics, UC Davis. Built as the extraction engine behind [Scholr](https://usescholr.com), an AI academic co-pilot for students.
