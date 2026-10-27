"""Web app: upload a syllabus, review what was found, download a calendar file.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import os
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from syllabus_planner.cli import run_extraction
from syllabus_planner.ics import to_ics
from syllabus_planner.schema import Deadline, GradeComponent, ItemType, Syllabus
from syllabus_planner.validate import check

st.set_page_config(page_title="Syllabus Planner", page_icon="🗓️", layout="centered")
st.title("Syllabus → Semester Planner")
st.caption("Upload a syllabus PDF. Review every deadline and grade weight, fix anything wrong, then add it all to your calendar.")


def term_options() -> list[str]:
    year = date.today().year
    return [f"{season} {y}" for y in (year, year + 1) for season in ("Winter", "Spring", "Summer", "Fall")]


uploaded = st.file_uploader("Syllabus PDF", type=["pdf"])
col1, col2 = st.columns(2)
default_term = f"Fall {date.today().year}"
term = col1.selectbox("Term", term_options(), index=term_options().index(default_term))
def find_api_key() -> str | None:
    """Local runs use the environment variable; Streamlit Cloud uses app secrets."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:  # no secrets file configured
        return None


api_key = find_api_key()
if api_key:
    os.environ["ANTHROPIC_API_KEY"] = api_key
has_key = bool(api_key)
method = col2.radio(
    "Extractor",
    ["llm", "baseline"],
    format_func=lambda m: "AI (Claude)" if m == "llm" else "Rules only (no API key)",
    index=0 if has_key else 1,
    horizontal=True,
)

if uploaded and st.button("Extract", type="primary"):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(uploaded.getvalue())
        path = Path(tmp.name)
    try:
        with st.spinner("Reading the syllabus..."):
            st.session_state["syllabus"] = run_extraction(path, term, method)
            st.session_state["term"] = term
    except Exception as err:  # show a readable error instead of a stack trace
        st.error(f"Extraction failed: {err}")
    finally:
        path.unlink(missing_ok=True)

syllabus: Syllabus | None = st.session_state.get("syllabus")
if syllabus:
    st.subheader(" ".join(x for x in (syllabus.course_code, syllabus.course_title) if x) or "Extracted syllabus")

    for warning in check(syllabus, st.session_state.get("term")):
        st.warning(warning)

    st.markdown("**Deadlines** (edit, add or delete rows before exporting)")
    deadlines_df = pd.DataFrame(
        [{"title": d.title, "type": d.type.value, "due_date": d.due_date, "due_time": d.due_time or "", "source_text": d.source_text or ""} for d in syllabus.deadlines],
        columns=["title", "type", "due_date", "due_time", "source_text"],
    )
    edited_deadlines = st.data_editor(
        deadlines_df,
        num_rows="dynamic",
        width="stretch",
        column_config={
            "type": st.column_config.SelectboxColumn(options=[t.value for t in ItemType]),
            "due_date": st.column_config.DateColumn(format="ddd MMM D, YYYY"),
            "due_time": st.column_config.TextColumn(help="Optional, 24h HH:MM"),
            "source_text": st.column_config.TextColumn("From syllabus", disabled=True),
        },
        key="deadlines_editor",
    )

    st.markdown("**Grade breakdown**")
    comps_df = pd.DataFrame([c.model_dump() for c in syllabus.grade_components], columns=["name", "weight_pct"])
    edited_comps = st.data_editor(comps_df, num_rows="dynamic", width="stretch", key="comps_editor")
    if len(edited_comps):
        st.caption(f"Total: {edited_comps['weight_pct'].fillna(0).sum():g}%")

    # Rebuild the syllabus from the edited tables so the export reflects the student's fixes.
    reviewed = Syllabus(
        course_code=syllabus.course_code,
        course_title=syllabus.course_title,
        term=syllabus.term,
        grade_components=[GradeComponent(name=r["name"], weight_pct=float(r["weight_pct"])) for _, r in edited_comps.dropna().iterrows()],
        deadlines=[
            Deadline(title=r["title"], type=r["type"], due_date=r["due_date"], due_time=r["due_time"] or None, source_text=r["source_text"] or None)
            for _, r in edited_deadlines.dropna(subset=["title", "due_date"]).iterrows()
        ],
    )
    filename = (syllabus.course_code or "syllabus").replace(" ", "_") + ".ics"
    st.download_button("Download calendar (.ics)", to_ics(reviewed), file_name=filename, mime="text/calendar", type="primary")
    st.caption("Import the .ics into Google Calendar (Settings → Import), Apple Calendar or Outlook.")
