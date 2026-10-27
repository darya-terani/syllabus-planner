"""Generate a fictional sample syllabus PDF for demos and tests.

It is invented on purpose (no real course or professor), so it is safe to
commit to a public repo. It includes the tricky cases real syllabi have:
a schedule table, dates without a year, a holiday that is not a deadline,
a recurring quiz with no listed dates, and a deadline mentioned twice.
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

OUT = Path(__file__).resolve().parent.parent / "examples" / "sample_syllabus.pdf"


def build() -> None:
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(OUT), pagesize=letter, title="DSC 101 Sample Syllabus")
    story = [
        Paragraph("DSC 101: Introduction to Applied Data Analysis", styles["Title"]),
        Paragraph("Fall 2026 · Fictional course for demonstration purposes", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Course Description", styles["Heading2"]),
        Paragraph(
            "An introduction to cleaning, visualizing and modeling real data in Python. "
            "Short quizzes are given in section every Friday. Lectures are Tuesday and Thursday.",
            styles["Normal"],
        ),
        Paragraph("Grading", styles["Heading2"]),
        Paragraph("Homework 25%", styles["Normal"]),
        Paragraph("Quizzes 10%", styles["Normal"]),
        Paragraph("Midterm Exam 20%", styles["Normal"]),
        Paragraph("Final Project 20%", styles["Normal"]),
        Paragraph("Final Exam 25%", styles["Normal"]),
        Spacer(1, 12),
        Paragraph("Important Dates", styles["Heading2"]),
        Paragraph(
            "The midterm exam is on Thursday, Oct. 22 in class. The final project report is due "
            "Friday, December 4 at 11:59 PM. The final exam is on December 10 at 10:30.",
            styles["Normal"],
        ),
        Spacer(1, 12),
        Paragraph("Schedule", styles["Heading2"]),
    ]
    rows = [
        ["Week", "Date", "Topic", "Due"],
        ["1", "9/24", "Course overview, Python setup", ""],
        ["2", "10/1", "Data cleaning with pandas", "HW 1 due 10/2"],
        ["3", "10/8", "Visualization", "HW 2 due 10/9"],
        ["4", "10/15", "Probability review", "Project proposal due 10/16"],
        ["5", "10/22", "Midterm exam (in class)", ""],
        ["6", "10/29", "Linear regression", "HW 3 due 10/30"],
        ["7", "11/5", "Classification", "HW 4 due 11/6"],
        ["8", "11/11", "Veterans Day - no class", ""],
        ["9", "11/19", "Model evaluation", "HW 5 due 11/20"],
        ["10", "12/3", "Project presentations", "Final project report due 12/4"],
    ]
    table = Table(rows, colWidths=[40, 50, 200, 170])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    OUT.parent.mkdir(exist_ok=True)
    build()
