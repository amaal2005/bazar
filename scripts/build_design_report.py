"""Build a three-page PDF from the Markdown design report."""

import re
from html import escape
from pathlib import Path

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "design-report.md"
OUTPUT = ROOT / "docs" / "design-report.pdf"

styles = {
    "title": ParagraphStyle(
        "Title",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#17324d"),
        spaceAfter=10,
    ),
    "heading": ParagraphStyle(
        "Heading",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=15,
        spaceBefore=12,
        spaceAfter=6,
        textColor=colors.HexColor("#17324d"),
        keepWithNext=True,
    ),
    "body": ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=10.5,
        leading=14.5,
        spaceAfter=8,
        alignment=TA_LEFT,
    ),
    "code": ParagraphStyle(
        "Code",
        fontName="Courier",
        fontSize=8,
        leading=11,
        backColor=colors.HexColor("#f1f4f7"),
        borderPadding=7,
        spaceBefore=4,
        spaceAfter=9,
    ),
}


def normalize(text):
    for character in ("\u2014", "\u2013", "\u2011"):
        text = text.replace(character, "-")
    return text.replace("\u2019", "'")


def footer(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#cbd5df"))
    canvas.line(20 * mm, 17 * mm, 190 * mm, 17 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#536579"))
    canvas.drawString(20 * mm, 12 * mm, "Bazar.com | Design Report")
    canvas.drawRightString(
        190 * mm, 12 * mm, f"Page {document.page}"
    )
    canvas.restoreState()


def main():
    text = normalize(SOURCE.read_text(encoding="utf-8"))
    story = []
    paragraph = []
    code_lines = []
    in_code = False

    def flush_paragraph():
        if paragraph:
            story.append(Paragraph(
                escape(" ".join(paragraph)), styles["body"]
            ))
            paragraph.clear()

    for line in text.splitlines():
        if line.startswith("```"):
            flush_paragraph()
            if in_code:
                story.append(Preformatted(
                    "\n".join(code_lines), styles["code"]
                ))
                code_lines.clear()
            in_code = not in_code
            continue

        if in_code:
            code_lines.append(line)
            continue

        if line.startswith("# "):
            flush_paragraph()
            story.append(Paragraph(
                escape(line[2:]), styles["title"]
            ))
        elif line.startswith("## "):
            flush_paragraph()
            # Page 1: sections 1-2; page 2: 3-5; page 3: 6-7.
            if re.match(r"## (3|6)\.", line):
                story.append(PageBreak())
            story.append(Paragraph(
                escape(line[3:]), styles["heading"]
            ))
        elif not line.strip():
            flush_paragraph()
        else:
            paragraph.append(line.strip())

    flush_paragraph()
    assert not in_code, "Unclosed Markdown code block."

    document = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=17 * mm,
        bottomMargin=23 * mm,
        title="Bazar.com - Design Report",
        author="Bazar.com Project Team",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)

    reader = PdfReader(OUTPUT)
    pages = len(reader.pages)
    print(f"Created: {OUTPUT}")
    print(f"Pages: {pages}")
    assert pages == 3, "Unexpected page count; review layout."
    assert all(page.extract_text().strip() for page in reader.pages)
    print("PASS: Three nonempty pages generated.")


if __name__ == "__main__":
    main()
