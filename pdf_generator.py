"""
Professional Study Guide PDF Generator using ReportLab.
Converts markdown study notes into clean, printable, textbook-style PDFs.
"""

import os
import re
from datetime import datetime
from typing import Optional, List

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, KeepTogether, PageBreak
)
from reportlab.pdfgen import canvas


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and print 'Page X of Y'."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))  # Slate gray

        # Running header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, letter[1] - 36, "YouTube Lecture Study Notes")
            self.setStrokeColor(colors.HexColor("#E2E8F0"))
            self.setLineWidth(0.5)
            self.line(54, letter[1] - 42, letter[0] - 54, letter[1] - 42)

        # Running footer
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(letter[0] - 54, 32, page_str)
        self.drawString(54, 32, "Confidential & Educational • Generated with AI Study Tool")
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(54, 42, letter[0] - 54, 42)

        self.restoreState()


def create_study_pdf(
    title: str,
    channel: str,
    markdown_content: str,
    output_path: str,
    playlist_title: Optional[str] = None
) -> str:
    """
    Render markdown study notes into a polished PDF document.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    
    # 54pt = 0.75 in margins
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()

    # Custom Palettes
    PRIMARY_COLOR = colors.HexColor("#1E3A8A")    # Deep Blue
    SECONDARY_COLOR = colors.HexColor("#0D9488")  # Teal Accent
    TEXT_DARK = colors.HexColor("#0F172A")        # Dark Slate
    BG_CALLOUT = colors.HexColor("#F8FAFC")       # Off-white / light slate
    BORDER_CALLOUT = colors.HexColor("#3B82F6")   # Sky Blue Border

    # Typography styles
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#475569"),
        spaceAfter=14
    ))

    styles.add(ParagraphStyle(
        'SectionH1',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=PRIMARY_COLOR,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=SECONDARY_COLOR,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    ))

    styles.add(ParagraphStyle(
        'StudyBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT_DARK,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        'StudyBullet',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=TEXT_DARK,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=3
    ))

    styles.add(ParagraphStyle(
        'CalloutText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#1E293B")
    ))

    styles.add(ParagraphStyle(
        'CodeSnippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#1E293B")
    ))

    story = []

    # Title Banner Block
    if playlist_title:
        story.append(Paragraph(f"<b>SERIES / PLAYLIST:</b> {playlist_title.upper()}", styles['DocMeta']))
    
    story.append(Paragraph(title, styles['DocTitle']))
    
    now_str = datetime.now().strftime("%B %d, %Y")
    meta_text = f"<b>Instructor / Channel:</b> {channel} &nbsp;&nbsp;|&nbsp;&nbsp; <b>Date Generated:</b> {now_str}"
    story.append(Paragraph(meta_text, styles['DocMeta']))
    
    # Divider bar
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY_COLOR, spaceBefore=2, spaceAfter=12))

    # Parse markdown into Flowables
    lines = markdown_content.split('\n')
    i = 0
    in_code_block = False
    code_lines = []

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Handle Code Blocks ```
        if stripped.startswith('```'):
            if in_code_block:
                # Close code block
                in_code_block = False
                code_text = "<br/>".join(escape_html(l) for l in code_lines)
                code_p = Paragraph(code_text, styles['CodeSnippet'])
                t = Table([[code_p]], colWidths=[doc.width])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ]))
                story.append(t)
                story.append(Spacer(1, 6))
                code_lines = []
            else:
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        if not stripped:
            i += 1
            continue

        # Page break tags
        if stripped.lower() in ['[pagebreak]', '\\pagebreak', '<!-- pagebreak -->', '<pagebreak>']:
            story.append(PageBreak())
            i += 1
            continue

        # Horizontal divider rules
        if stripped in ['---', '***', '___']:
            story.append(Spacer(1, 4))
            story.append(HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#CBD5E1"), spaceBefore=4, spaceAfter=8))
            i += 1
            continue

        # Ignore redundant top-level # Title if present in markdown
        if stripped.startswith('# ') and not stripped.startswith('## '):
            i += 1
            continue

        # Level 1 Heading (##)
        if stripped.startswith('## '):
            heading_text = clean_inline_markdown(stripped[3:])
            story.append(Spacer(1, 4))
            story.append(Paragraph(heading_text, styles['SectionH1']))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0"), spaceBefore=1, spaceAfter=4))
            i += 1
            continue

        # Level 2 Heading (###)
        if stripped.startswith('### '):
            heading_text = clean_inline_markdown(stripped[4:])
            story.append(Paragraph(heading_text, styles['SectionH2']))
            i += 1
            continue

        # Blockquote / Callout (> )
        if stripped.startswith('> '):
            quote_text = clean_inline_markdown(stripped[2:])
            callout_p = Paragraph(f"<b>Key Note:</b> {quote_text}", styles['CalloutText'])
            t = Table([[callout_p]], colWidths=[doc.width])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), BG_CALLOUT),
                ('LINEBEFORE', (0, 0), (0, -1), 3, BORDER_CALLOUT),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ]))
            story.append(t)
            story.append(Spacer(1, 4))
            i += 1
            continue

        # Bullet List (- or * or •)
        if stripped.startswith(('- ', '* ', '• ')):
            bullet_text = clean_inline_markdown(stripped[2:])
            formatted_bullet = f"&bull; &nbsp;{bullet_text}"
            story.append(Paragraph(formatted_bullet, styles['StudyBullet']))
            i += 1
            continue

        # Numbered List (1. , 2. )
        num_match = re.match(r'^(\d+)\.\s+(.*)$', stripped)
        if num_match:
            num = num_match.group(1)
            item_text = clean_inline_markdown(num_match.group(2))
            formatted_num = f"<b>{num}.</b> &nbsp;{item_text}"
            story.append(Paragraph(formatted_num, styles['StudyBullet']))
            i += 1
            continue

        # Standard Paragraph
        body_text = clean_inline_markdown(stripped)
        story.append(Paragraph(body_text, styles['StudyBody']))
        i += 1

    # Build the PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path


def escape_html(text: str) -> str:
    """Escape special HTML characters for ReportLab Paragraphs."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def clean_inline_markdown(text: str) -> str:
    """Convert common inline markdown (bold, italic, code tags) into ReportLab HTML tags."""
    # Escape raw XML characters first
    text = escape_html(text)
    
    # Bold: **word** or __word__
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.*?)__', r'<b>\1</b>', text)
    
    # Italic: *word* or _word_
    text = re.sub(r'(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # Inline code: `code`
    text = re.sub(r'`(.*?)`', r'<font face="Courier" color="#0369A1">\1</font>', text)
    
    return text
