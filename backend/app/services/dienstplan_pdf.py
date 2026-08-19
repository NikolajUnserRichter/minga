"""
Dienstplan als PDF-Aushang.

Ein Blatt Querformat pro Zeitraum: je Tag eine Spalte mit den Schichten und
darunter den Zusatzaufgaben. Bewusst großzügig gesetzt — das Blatt hängt am
Schwarzen Brett und wird aus zwei Metern Entfernung gelesen.
"""
from datetime import date, timedelta
from io import BytesIO
from typing import Optional, Sequence
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.staff import StaffShift, StaffTask

WEEKDAYS = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]


def _shift_line(shift: StaffShift) -> str:
    if shift.start_time and shift.end_time:
        zeit = f"{shift.start_time}–{shift.end_time}"
    elif shift.start_time:
        zeit = f"ab {shift.start_time}"
    else:
        zeit = "ganztags"
    text = f"<b>{escape(shift.employee_name)}</b><br/>{escape(zeit)}"
    if shift.aufgabe:
        text += f" · {escape(shift.aufgabe)}"
    return text


def _task_line(task: StaffTask) -> str:
    # Kästchen als ASCII — Helvetica hat keine Unicode-Checkboxen
    marker = "[x]" if task.erledigt else "[  ]"
    text = f"{marker} {escape(task.titel)}"
    if task.employee_name:
        text += f" ({escape(task.employee_name)})"
    return text


def _iso_kw(tag: date) -> int:
    return tag.isocalendar()[1]


def generate_dienstplan_pdf(
    shifts: Sequence[StaffShift],
    tasks: Sequence[StaffTask],
    von_datum: date,
    bis_datum: date,
    settings: Optional[dict] = None,
) -> bytes:
    """Rendert den Dienstplan des Zeitraums als PDF (Bytes)."""
    settings = settings or {}
    tage = [von_datum + timedelta(days=i) for i in range((bis_datum - von_datum).days + 1)]

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=1.2 * cm, rightMargin=1.2 * cm,
        topMargin=1.2 * cm, bottomMargin=1.2 * cm,
        title="Dienstplan",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PlanTitle", parent=styles["Title"], fontSize=20, spaceAfter=2)
    sub_style = ParagraphStyle("PlanSub", parent=styles["Normal"], fontSize=11, textColor=colors.grey)
    cell_style = ParagraphStyle("PlanCell", parent=styles["Normal"], fontSize=9.5, leading=12)
    head_style = ParagraphStyle("PlanHead", parent=styles["Normal"], fontSize=11, leading=13,
                                alignment=1, textColor=colors.white)
    task_head_style = ParagraphStyle("PlanTaskHead", parent=styles["Normal"], fontSize=8,
                                     leading=10, textColor=colors.grey)

    firma = settings.get("COMPANY_NAME") or "Minga Greens"
    if _iso_kw(von_datum) == _iso_kw(bis_datum):
        zeitraum = f"KW {_iso_kw(von_datum)} · {von_datum:%d.%m.%Y} – {bis_datum:%d.%m.%Y}"
    else:
        zeitraum = f"{von_datum:%d.%m.%Y} – {bis_datum:%d.%m.%Y}"

    body = [
        Paragraph("Dienstplan", title_style),
        Paragraph(f"{escape(firma)} · {zeitraum}", sub_style),
        Spacer(1, 10),
    ]

    header_row = [
        Paragraph(f"<b>{WEEKDAYS[t.weekday()]}</b><br/>{t:%d.%m.}", head_style)
        for t in tage
    ]

    shift_row = []
    task_row = []
    for tag in tage:
        tages_shifts = [s for s in shifts if s.datum == tag]
        shift_row.append(
            Paragraph("<br/><br/>".join(_shift_line(s) for s in tages_shifts), cell_style)
            if tages_shifts else Paragraph("<i>frei</i>", cell_style)
        )

        tages_tasks = [t for t in tasks if t.datum == tag]
        if tages_tasks:
            task_row.append(Paragraph(
                "<br/>".join(_task_line(t) for t in tages_tasks), cell_style
            ))
        else:
            task_row.append(Paragraph("—", cell_style))

    spalten = len(tage)
    verfuegbar = landscape(A4)[0] - 2.4 * cm
    col_width = verfuegbar / spalten

    table = Table(
        [header_row, shift_row,
         [Paragraph("<b>Aufgaben</b>", task_head_style)] + [""] * (spalten - 1),
         task_row],
        colWidths=[col_width] * spalten,
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4a7c3f")),
        ("SPAN", (0, 2), (-1, 2)),
        ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#f0f0f0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, 1), 6),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    body.append(table)

    body.append(Spacer(1, 10))
    body.append(Paragraph(
        f"<font size=8 color='grey'>Stand: {date.today():%d.%m.%Y} · "
        "Änderungen bitte im ERP eintragen, nicht auf dem Aushang.</font>",
        styles["Normal"],
    ))

    doc.build(body)
    return buffer.getvalue()
