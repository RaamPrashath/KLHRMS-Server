"""
Attendance export service.

Generates Excel, PDF, and CSV files from a list of attendance records
passed directly from the frontend (the currently visible page).

Dependencies: openpyxl, reportlab
"""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Literal

import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.attendance.export_schema import AttendanceExportRow

# ─── Shared helpers ───────────────────────────────────────────────────────────

ExportFormat = Literal["xlsx", "pdf", "csv"]

# Brand green used in headers
_GREEN = "00874A"
_GREEN_LIGHT = "D4F5E4"
_GREY_HEADER = "F5F5F7"

_COLUMNS_SELF = ["Date", "Clock In", "Clock Out", "Total Hrs", "Status"]
_COLUMNS_ORG = ["Employee", "Date", "Clock In", "Clock Out", "Total Hrs", "Status"]


def _fmt_datetime(iso: str | None) -> str:
    """Format an ISO datetime string to HH:MM AM/PM (IST display)."""
    if not iso:
        return "—"
    try:
        # Normalize naive datetimes to UTC
        normalized = iso if (iso.endswith("Z") or "+" in iso) else f"{iso}Z"
        dt = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
        # Convert to IST (+5:30)
        from datetime import timezone, timedelta
        ist = timezone(timedelta(hours=5, minutes=30))
        dt_ist = dt.astimezone(ist)
        return dt_ist.strftime("%I:%M %p")
    except Exception:
        return iso or "—"


def _fmt_date(iso_date: str | None) -> str:
    if not iso_date:
        return "—"
    try:
        from datetime import date
        d = date.fromisoformat(iso_date)
        # Use lstrip to remove leading zero — cross-platform safe
        return f"{d.day} {d.strftime('%b')} {d.year}"
    except Exception:
        return iso_date or "—"


def _fmt_hours(hours: float | None) -> str:
    if hours is None:
        return "—"
    return f"{hours:.1f}"


def _status_label(status: str) -> str:
    return {"PRESENT": "Present", "HALF_DAY": "Half Day", "ABSENT": "Absent"}.get(
        status, status
    )


def _build_rows(
    records: list[AttendanceExportRow], show_employee: bool
) -> tuple[list[str], list[list[str]]]:
    """Return (headers, data_rows) as plain strings."""
    headers = _COLUMNS_ORG if show_employee else _COLUMNS_SELF
    rows: list[list[str]] = []
    for r in records:
        row: list[str] = []
        if show_employee:
            row.append(r.employeeName or "—")
        row += [
            _fmt_date(r.date),
            _fmt_datetime(r.clockIn),
            _fmt_datetime(r.clockOut),
            _fmt_hours(r.totalHours),
            _status_label(r.status),
        ]
        rows.append(row)
    return headers, rows


# ─── Excel ────────────────────────────────────────────────────────────────────


def generate_xlsx(
    records: list[AttendanceExportRow],
    show_employee: bool,
    title: str,
) -> bytes:
    headers, rows = _build_rows(records, show_employee)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance"

    # ── Title row ──────────────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    title_cell.fill = PatternFill("solid", fgColor=_GREEN)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # ── Header row ─────────────────────────────────────────────────────────────
    header_fill = PatternFill("solid", fgColor=_GREEN_LIGHT)
    header_font = Font(name="Calibri", bold=True, size=10, color="1D1D1F")
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header.upper())
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 20

    # ── Data rows ──────────────────────────────────────────────────────────────
    status_fills = {
        "Present": PatternFill("solid", fgColor="E6F4EA"),
        "Half Day": PatternFill("solid", fgColor="FEF7E0"),
        "Absent": PatternFill("solid", fgColor="FCE8E6"),
    }
    status_fonts = {
        "Present": Font(name="Calibri", size=10, color="1E7E34"),
        "Half Day": Font(name="Calibri", size=10, color="A07000"),
        "Absent": Font(name="Calibri", size=10, color="B31412"),
    }
    default_font = Font(name="Calibri", size=10)

    for row_idx, row_data in enumerate(rows, start=3):
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            # Status column is always last
            if col_idx == len(headers):
                cell.font = status_fonts.get(value, default_font)
                cell.fill = status_fills.get(value, PatternFill())
            else:
                cell.font = default_font
        ws.row_dimensions[row_idx].height = 18

    # ── Column widths ──────────────────────────────────────────────────────────
    col_widths = {
        "Employee": 24,
        "Date": 16,
        "Clock In": 14,
        "Clock Out": 14,
        "Total Hrs": 12,
        "Status": 14,
    }
    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(
            header, 14
        )

    # ── Freeze panes below header ──────────────────────────────────────────────
    ws.freeze_panes = "A3"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── PDF ──────────────────────────────────────────────────────────────────────


def generate_pdf(
    records: list[AttendanceExportRow],
    show_employee: bool,
    title: str,
) -> bytes:
    headers, rows = _build_rows(records, show_employee)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # ── Title ──────────────────────────────────────────────────────────────────
    title_style = styles["Title"]
    title_style.fontSize = 14
    title_style.textColor = colors.HexColor(f"#{_GREEN}")
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 6 * mm))

    # ── Table data ─────────────────────────────────────────────────────────────
    table_data = [headers] + rows

    # Column widths — distribute across landscape A4 (~267mm usable)
    usable_mm = 267
    if show_employee:
        col_widths_mm = [50, 35, 30, 30, 25, 30]
    else:
        col_widths_mm = [40, 35, 35, 30, 35]

    # Normalize to fill usable width
    total = sum(col_widths_mm)
    col_widths_pt = [(w / total) * usable_mm * mm for w in col_widths_mm]

    tbl = Table(table_data, colWidths=col_widths_pt, repeatRows=1)

    brand_green = colors.HexColor(f"#{_GREEN}")
    light_green = colors.HexColor(f"#{_GREEN_LIGHT}")
    grey_row = colors.HexColor("#F5F5F7")

    tbl_style = TableStyle(
        [
            # Header
            ("BACKGROUND", (0, 0), (-1, 0), brand_green),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUND", (0, 1), (-1, -1), [grey_row, colors.white]),
            # Data rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 8),
            ("ALIGN", (0, 1), (-1, -1), "CENTER"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#E5E5EA")),
            ("LINEBELOW", (0, 0), (-1, 0), 1, brand_green),
            # Padding
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]
    )

    # Status column color coding (always last column)
    status_col = len(headers) - 1
    for row_idx, row_data in enumerate(rows, start=1):
        status_val = row_data[-1]
        if status_val == "Present":
            tbl_style.add("BACKGROUND", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#E6F4EA"))
            tbl_style.add("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#1E7E34"))
        elif status_val == "Half Day":
            tbl_style.add("BACKGROUND", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#FEF7E0"))
            tbl_style.add("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#A07000"))
        elif status_val == "Absent":
            tbl_style.add("BACKGROUND", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#FCE8E6"))
            tbl_style.add("TEXTCOLOR", (status_col, row_idx), (status_col, row_idx), colors.HexColor("#B31412"))

    tbl.setStyle(tbl_style)
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()


# ─── CSV ──────────────────────────────────────────────────────────────────────


def generate_csv(
    records: list[AttendanceExportRow],
    show_employee: bool,
) -> bytes:
    headers, rows = _build_rows(records, show_employee)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)

    return buf.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility


def _fmt_work_log_text(value: str | None) -> str:
    if not value:
        return "—"
    return " ".join(value.split())


def _build_work_log_report_rows(
    records: list[object],
) -> tuple[list[str], list[list[str]]]:
    headers = [
        "Employee Name",
        "Date",
        "Clock In",
        "Clock Out",
        "Total Hours",
        "Department",
        "Team",
        "Project",
        "Task",
        "Daily Work Log",
    ]
    rows: list[list[str]] = []
    for record in records:
        rows.append(
            [
                getattr(record, "employeeName", None) or "—",
                _fmt_date(getattr(record, "date", None).isoformat() if getattr(record, "date", None) else None),
                _fmt_datetime(getattr(record, "clockIn", None).isoformat() if getattr(record, "clockIn", None) else None),
                _fmt_datetime(getattr(record, "clockOut", None).isoformat() if getattr(record, "clockOut", None) else None),
                _fmt_hours(getattr(record, "totalHours", None)),
                getattr(record, "departmentName", None) or "—",
                getattr(record, "teamName", None) or "—",
                getattr(record, "projectName", None) or "—",
                getattr(record, "taskName", None) or "—",
                _fmt_work_log_text(getattr(record, "dailyWorkLog", None)),
            ]
        )
    return headers, rows


def generate_work_log_report_csv(records: list[object]) -> bytes:
    headers, rows = _build_work_log_report_rows(records)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def generate_work_log_report_xlsx(records: list[object], title: str) -> bytes:
    headers, rows = _build_work_log_report_rows(records)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Work Logs"

    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    title_cell.fill = PatternFill("solid", fgColor=_GREEN)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    header_fill = PatternFill("solid", fgColor=_GREEN_LIGHT)
    header_font = Font(name="Calibri", bold=True, size=10, color="1D1D1F")
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_idx, value=header.upper())
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    wrap_alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
    center_alignment = Alignment(horizontal="center", vertical="center")
    default_font = Font(name="Calibri", size=10)
    for row_idx, row_data in enumerate(rows, start=3):
        for col_idx, value in enumerate(row_data, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = default_font
            cell.alignment = wrap_alignment if col_idx == len(headers) else center_alignment
        ws.row_dimensions[row_idx].height = 34

    col_widths = {
        "Employee Name": 24,
        "Date": 16,
        "Clock In": 14,
        "Clock Out": 14,
        "Total Hours": 12,
        "Department": 18,
        "Team": 18,
        "Project": 18,
        "Task": 18,
        "Daily Work Log": 56,
    }
    for col_idx, header in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = col_widths.get(header, 16)

    ws.freeze_panes = "A3"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── Pivot helpers ────────────────────────────────────────────────────────────

def _fmt_pivot_date(ymd: str) -> str:
    """'2026-05-04' → 'May 4'"""
    try:
        from datetime import date as _date
        d = _date.fromisoformat(ymd)
        return f"{d.strftime('%b')} {d.day}"
    except Exception:
        return ymd


def _fmt_pivot_hours(hours: float | None) -> str:
    if hours is None:
        return "–"
    return f"{hours:.1f}h"


def _status_bg_font(status: str | None) -> tuple[str, str]:
    """Return (bg_hex, text_hex) for a status value."""
    if status == "PRESENT":
        return ("E6F4EA", "1E7E34")
    if status == "HALF_DAY":
        return ("FEF7E0", "A07000")
    if status == "ABSENT":
        return ("FCE8E6", "B31412")
    return ("FFFFFF", "AEAEB2")  # no record — white bg, grey text


# ─── Pivot Excel ──────────────────────────────────────────────────────────────


def generate_xlsx_pivot(pivot: "AttendancePivotExportPayload", title: str) -> bytes:
    from app.modules.attendance.export_schema import AttendancePivotExportPayload

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance"

    date_cols = pivot.dateColumns
    n_date_cols = len(date_cols)
    # Columns: Employee | date1 | date2 | ... | Total
    total_cols = 1 + n_date_cols + 1

    # ── Title row ──────────────────────────────────────────────────────────────
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=total_cols)
    tc = ws.cell(row=1, column=1, value=title)
    tc.font = Font(name="Calibri", bold=True, size=13, color="FFFFFF")
    tc.fill = PatternFill("solid", fgColor=_GREEN)
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    # ── Period label row ───────────────────────────────────────────────────────
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=total_cols)
    pc = ws.cell(row=2, column=1, value=pivot.periodLabel)
    pc.font = Font(name="Calibri", italic=True, size=9, color="6E6E73")
    pc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[2].height = 16

    # ── Header row ─────────────────────────────────────────────────────────────
    header_fill = PatternFill("solid", fgColor=_GREEN_LIGHT)
    header_font = Font(name="Calibri", bold=True, size=9, color="1D1D1F")

    ws.cell(row=3, column=1, value="EMPLOYEE").font = header_font
    ws.cell(row=3, column=1).fill = header_fill
    ws.cell(row=3, column=1).alignment = Alignment(horizontal="left", vertical="center")

    for i, ymd in enumerate(date_cols, start=2):
        c = ws.cell(row=3, column=i, value=_fmt_pivot_date(ymd))
        c.font = header_font
        c.fill = header_fill
        c.alignment = Alignment(horizontal="center", vertical="center")

    total_header = ws.cell(row=3, column=total_cols, value="TOTAL")
    total_header.font = header_font
    total_header.fill = header_fill
    total_header.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[3].height = 20

    # ── Data rows ──────────────────────────────────────────────────────────────
    default_font = Font(name="Calibri", size=9)
    bold_font = Font(name="Calibri", size=9, bold=True)

    for row_idx, emp_row in enumerate(pivot.rows, start=4):
        # Employee name
        name_cell = ws.cell(row=row_idx, column=1, value=emp_row.employeeName)
        name_cell.font = Font(name="Calibri", size=9, bold=True, color="1D1D1F")
        name_cell.alignment = Alignment(horizontal="left", vertical="center")

        # Build a quick lookup: date → cell
        cell_map = {c.date: c for c in emp_row.cells}

        for col_offset, ymd in enumerate(date_cols, start=2):
            cell_data = cell_map.get(ymd)
            hours = cell_data.totalHours if cell_data else None
            status = cell_data.status if cell_data else None
            display = _fmt_pivot_hours(hours)

            bg_hex, text_hex = _status_bg_font(status)
            xc = ws.cell(row=row_idx, column=col_offset, value=display)
            xc.font = Font(name="Calibri", size=9, color=text_hex)
            xc.fill = PatternFill("solid", fgColor=bg_hex)
            xc.alignment = Alignment(horizontal="center", vertical="center")

        # Total
        total_val = f"{emp_row.total:.1f}h" if emp_row.total > 0 else "–"
        tc2 = ws.cell(row=row_idx, column=total_cols, value=total_val)
        tc2.font = bold_font
        tc2.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[row_idx].height = 18

    # ── Column widths ──────────────────────────────────────────────────────────
    ws.column_dimensions["A"].width = 26
    for i in range(2, total_cols):
        ws.column_dimensions[get_column_letter(i)].width = 10
    ws.column_dimensions[get_column_letter(total_cols)].width = 10

    ws.freeze_panes = "B4"

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ─── Pivot PDF ────────────────────────────────────────────────────────────────


def generate_pdf_pivot(pivot: "AttendancePivotExportPayload", title: str) -> bytes:
    from reportlab.lib.pagesizes import A3
    from app.modules.attendance.export_schema import AttendancePivotExportPayload

    date_cols = pivot.dateColumns
    n_cols = len(date_cols)

    buf = io.BytesIO()

    # Use landscape A3 for monthly (many columns), landscape A4 for weekly
    page_size = landscape(A3) if n_cols > 10 else landscape(A4)

    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=12 * mm,
        rightMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
    )

    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = styles["Title"]
    title_style.fontSize = 13
    title_style.textColor = colors.HexColor(f"#{_GREEN}")
    story.append(Paragraph(title, title_style))

    # Period label
    period_style = styles["Normal"]
    period_style.fontSize = 9
    period_style.textColor = colors.HexColor("#6E6E73")
    story.append(Paragraph(pivot.periodLabel, period_style))
    story.append(Spacer(1, 5 * mm))

    # Build table data
    header_row = ["Employee"] + [_fmt_pivot_date(d) for d in date_cols] + ["Total"]
    table_data = [header_row]

    for emp_row in pivot.rows:
        cell_map = {c.date: c for c in emp_row.cells}
        data_row = [emp_row.employeeName]
        for ymd in date_cols:
            cell_data = cell_map.get(ymd)
            data_row.append(_fmt_pivot_hours(cell_data.totalHours if cell_data else None))
        total_str = f"{emp_row.total:.1f}h" if emp_row.total > 0 else "–"
        data_row.append(total_str)
        table_data.append(data_row)

    # Column widths
    usable_pt = (page_size[0] - 24 * mm)
    name_pt = 45 * mm
    total_pt = 14 * mm
    remaining_pt = usable_pt - name_pt - total_pt
    day_pt = max(remaining_pt / max(n_cols, 1), 8 * mm)
    col_widths_pt = [name_pt] + [day_pt] * n_cols + [total_pt]

    tbl = Table(table_data, colWidths=col_widths_pt, repeatRows=1)

    brand_green = colors.HexColor(f"#{_GREEN}")
    grey_row = colors.HexColor("#F5F5F7")

    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), brand_green),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 7),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUND", (0, 1), (-1, -1), [grey_row, colors.white]),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),  # employee name bold
        ("FONTNAME", (-1, 1), (-1, -1), "Helvetica-Bold"),  # total bold
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#E5E5EA")),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, brand_green),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]

    # Per-cell status coloring
    for row_idx, emp_row in enumerate(pivot.rows, start=1):
        cell_map = {c.date: c for c in emp_row.cells}
        for col_offset, ymd in enumerate(date_cols, start=1):
            cell_data = cell_map.get(ymd)
            status = cell_data.status if cell_data else None
            bg_hex, text_hex = _status_bg_font(status)
            if status is not None:  # only color cells that have data
                style_cmds.append(
                    ("BACKGROUND", (col_offset, row_idx), (col_offset, row_idx),
                     colors.HexColor(f"#{bg_hex}"))
                )
                style_cmds.append(
                    ("TEXTCOLOR", (col_offset, row_idx), (col_offset, row_idx),
                     colors.HexColor(f"#{text_hex}"))
                )

    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    doc.build(story)
    return buf.getvalue()


# ─── Pivot CSV ────────────────────────────────────────────────────────────────


def generate_csv_pivot(pivot: "AttendancePivotExportPayload") -> bytes:
    date_cols = pivot.dateColumns
    header_row = ["Employee"] + [_fmt_pivot_date(d) for d in date_cols] + ["Total"]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header_row)

    for emp_row in pivot.rows:
        cell_map = {c.date: c for c in emp_row.cells}
        data_row = [emp_row.employeeName]
        for ymd in date_cols:
            cell_data = cell_map.get(ymd)
            data_row.append(_fmt_pivot_hours(cell_data.totalHours if cell_data else None))
        total_str = f"{emp_row.total:.1f}h" if emp_row.total > 0 else "–"
        data_row.append(total_str)
        writer.writerow(data_row)

    return buf.getvalue().encode("utf-8-sig")
