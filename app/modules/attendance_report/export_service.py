from __future__ import annotations

import html
import io
import re
from collections import defaultdict
from datetime import date

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.modules.attendance_report.schema import (
    AttendanceReportExportEmployee,
    AttendanceReportExportRequest,
    AttendanceReportRow,
)

_HEADER_FILL = "1F4E78"
_TITLE_FILL = "D9EAF7"
_SUBTOTAL_FILL = "D9EAF7"
_THIN_BORDER = Side(style="thin", color="D9E2EC")
_GRID_BORDER = Border(left=_THIN_BORDER, right=_THIN_BORDER, top=_THIN_BORDER, bottom=_THIN_BORDER)
_REPORT_HEADERS = [
    "Date",
    "Day",
    "Project",
    "Description",
    "Hours",
    "Tickets on Hold / Pending Clarification",
]


def _employee_name(employee: AttendanceReportExportEmployee) -> str:
    return employee.name.strip() or employee.email or employee.id


def _safe_sheet_name(name: str, used: set[str]) -> str:
    cleaned = re.sub(r"[\[\]\:\*\?\/\\]", " ", name).strip() or "Employee"
    base = cleaned[:31]
    candidate = base
    counter = 2
    while candidate in used:
        suffix = f" {counter}"
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    used.add(candidate)
    return candidate


def _date_label(value: date) -> str:
    return value.isoformat()


def _day_label(value: date) -> str:
    return value.strftime("%A")


def _short_day_label(value: date) -> str:
    return value.strftime("%a")


def _display_hours(hours: float | None, force8: bool) -> float | str:
    if hours is None:
        return ""
    normalized = min(float(hours), 8.0) if force8 else float(hours)
    return round(normalized, 2)


def _numeric_hours(hours: float | None, force8: bool) -> float:
    value = _display_hours(hours, force8)
    return float(value) if isinstance(value, int | float) else 0.0


def _row_description(row: AttendanceReportRow) -> str:
    return row.clockOutDescription or ""


def _project_label(row: AttendanceReportRow) -> str:
    if row.projectName and row.taskName:
        return f"{row.projectName} - {row.taskName}"
    return row.projectName or row.taskName or ""


def _rows_by_employee(rows: list[AttendanceReportRow]) -> dict[str, list[AttendanceReportRow]]:
    grouped: dict[str, list[AttendanceReportRow]] = defaultdict(list)
    for row in rows:
        grouped[row.employeeId].append(row)
    for employee_rows in grouped.values():
        employee_rows.sort(key=lambda item: item.date)
    return grouped


def _employees_for_export(payload: AttendanceReportExportRequest) -> list[AttendanceReportExportEmployee]:
    if payload.employees:
        return sorted(payload.employees, key=lambda item: _employee_name(item).lower())
    seen: dict[str, AttendanceReportExportEmployee] = {}
    for row in payload.rows:
        seen[row.employeeId] = AttendanceReportExportEmployee(
            id=row.employeeId,
            name=row.employeeName,
            email=row.employeeEmail,
        )
    return sorted(seen.values(), key=lambda item: _employee_name(item).lower())


def _apply_report_sheet_layout(ws, last_row: int) -> None:
    widths = [14, 14, 22, 64, 12, 34]
    for index, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A3"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    for row in ws.iter_rows(min_row=1, max_row=last_row, max_col=len(_REPORT_HEADERS)):
        for cell in row:
            cell.border = _GRID_BORDER


def generate_report_xlsx(payload: AttendanceReportExportRequest) -> bytes:
    wb = openpyxl.Workbook()
    default_sheet = wb.active
    wb.remove(default_sheet)

    grouped = _rows_by_employee(payload.rows)
    used_sheet_names: set[str] = set()
    employees = _employees_for_export(payload)

    if not employees:
        employees = [AttendanceReportExportEmployee(id="empty", name="No selected employees")]

    for employee in employees:
        employee_rows = grouped.get(employee.id, [])
        ws = wb.create_sheet(_safe_sheet_name(_employee_name(employee), used_sheet_names))

        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(_REPORT_HEADERS))
        title_cell = ws.cell(row=1, column=1, value=f"Name: {_employee_name(employee)}")
        title_cell.font = Font(bold=True, size=12, color="1D1D1F")
        title_cell.fill = PatternFill("solid", fgColor=_TITLE_FILL)
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 24

        for col, header in enumerate(_REPORT_HEADERS, start=1):
            cell = ws.cell(row=2, column=col, value=header)
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor=_HEADER_FILL)
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        ws.row_dimensions[2].height = 24

        for row_index, row in enumerate(employee_rows, start=3):
            values = [
                _date_label(row.date),
                _day_label(row.date),
                _project_label(row),
                _row_description(row),
                _display_hours(row.totalHours, payload.force8),
                "",
            ]
            for col, value in enumerate(values, start=1):
                cell = ws.cell(row=row_index, column=col, value=value)
                cell.alignment = Alignment(
                    horizontal="left" if col in {3, 4, 6} else "center",
                    vertical="top",
                    wrap_text=col in {4, 6},
                )
                if col == 5 and value != "":
                    cell.number_format = "0.00"
            ws.row_dimensions[row_index].height = max(24, min(96, 18 + (_row_description(row).count("\n") + 1) * 12))

        total_row = len(employee_rows) + 3
        ws.cell(row=total_row, column=4, value="Total Hours:")
        ws.cell(row=total_row, column=4).font = Font(bold=True)
        if employee_rows:
            ws.cell(row=total_row, column=5, value=f"=SUM(E3:E{total_row - 1})")
        else:
            ws.cell(row=total_row, column=5, value="")
        ws.cell(row=total_row, column=5).font = Font(bold=True)
        ws.cell(row=total_row, column=5).number_format = "0.00"
        for col in range(1, len(_REPORT_HEADERS) + 1):
            cell = ws.cell(row=total_row, column=col)
            cell.fill = PatternFill("solid", fgColor=_SUBTOTAL_FILL)
            cell.alignment = Alignment(horizontal="center", vertical="center")
        _apply_report_sheet_layout(ws, total_row)

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _build_timesheet_maps(
    payload: AttendanceReportExportRequest,
) -> tuple[list[date], list[AttendanceReportExportEmployee], dict[str, dict[date, AttendanceReportRow]]]:
    dates = payload.dateColumns or sorted({row.date for row in payload.rows})
    employees = _employees_for_export(payload)
    grouped: dict[str, dict[date, AttendanceReportRow]] = defaultdict(dict)
    for row in payload.rows:
        grouped[row.employeeId][row.date] = row
    return dates, employees, grouped


def generate_timesheet_xlsx(payload: AttendanceReportExportRequest) -> bytes:
    dates, employees, grouped = _build_timesheet_maps(payload)
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = (payload.title or "Timesheet")[:31]

    total_cols = len(dates) + 2
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(total_cols, 2))
    title_cell = ws.cell(row=1, column=1, value=payload.title)
    title_cell.font = Font(bold=True, size=13, color="1D1D1F")
    title_cell.fill = PatternFill("solid", fgColor=_TITLE_FILL)
    title_cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.cell(row=2, column=1, value="Employee")
    ws.cell(row=2, column=2, value="Total Hours")
    for offset, day in enumerate(dates, start=3):
        ws.cell(row=2, column=offset, value=str(day.day))
        ws.cell(row=3, column=offset, value=_short_day_label(day))
    ws.cell(row=3, column=1, value="Day:")
    ws.cell(row=3, column=2, value="")

    for row in (2, 3):
        for col in range(1, total_cols + 1):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(bold=True, color="FFFFFF" if row == 2 else "1D1D1F")
            cell.fill = PatternFill("solid", fgColor=_HEADER_FILL if row == 2 else _TITLE_FILL)
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = _GRID_BORDER

    for row_index, employee in enumerate(employees, start=4):
        employee_rows = grouped.get(employee.id, {})
        ws.cell(row=row_index, column=1, value=_employee_name(employee))
        ws.cell(row=row_index, column=2, value=f"=SUM(C{row_index}:{get_column_letter(total_cols)}{row_index})")
        ws.cell(row=row_index, column=2).number_format = "0.00"
        for offset, day in enumerate(dates, start=3):
            report_row = employee_rows.get(day)
            value = _display_hours(report_row.totalHours, payload.force8) if report_row else ""
            cell = ws.cell(row=row_index, column=offset, value=value)
            if value != "":
                cell.number_format = "0.00"
        for col in range(1, total_cols + 1):
            cell = ws.cell(row=row_index, column=col)
            cell.border = _GRID_BORDER
            cell.alignment = Alignment(horizontal="left" if col == 1 else "center", vertical="center")
        ws.row_dimensions[row_index].height = 22

    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 13
    for col in range(3, total_cols + 1):
        ws.column_dimensions[get_column_letter(col)].width = 8
    ws.freeze_panes = "C4"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True

    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _paragraph(value: str, style: ParagraphStyle) -> Paragraph:
    escaped = html.escape(value or "").replace("\n", "<br/>")
    return Paragraph(escaped or "&nbsp;", style)


def generate_report_pdf(payload: AttendanceReportExportRequest) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )
    styles = getSampleStyleSheet()
    normal = ParagraphStyle("ReportCell", parent=styles["Normal"], fontSize=8, leading=10)
    title_style = ParagraphStyle("ReportTitle", parent=styles["Heading2"], fontSize=12, leading=14)

    grouped = _rows_by_employee(payload.rows)
    story = []
    employees = _employees_for_export(payload)
    for employee_index, employee in enumerate(employees):
        if employee_index:
            story.append(PageBreak())
        story.append(Paragraph(f"Name: {_employee_name(employee)}", title_style))
        if payload.periodLabel:
            story.append(Paragraph(html.escape(payload.periodLabel), normal))
        story.append(Spacer(1, 4 * mm))

        table_data: list[list[object]] = [_REPORT_HEADERS]
        for row in grouped.get(employee.id, []):
            table_data.append(
                [
                    _date_label(row.date),
                    _day_label(row.date),
                    _project_label(row),
                    _paragraph(_row_description(row), normal),
                    _display_hours(row.totalHours, payload.force8),
                    "",
                ]
            )
        total = sum(_numeric_hours(row.totalHours, payload.force8) for row in grouped.get(employee.id, []))
        table_data.append(["", "", "", "Total Hours:", f"{total:.2f}" if total else "", ""])

        table = Table(
            table_data,
            colWidths=[24 * mm, 24 * mm, 38 * mm, 108 * mm, 18 * mm, 54 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{_HEADER_FILL}")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E2EC")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (2, -1), "CENTER"),
                    ("ALIGN", (4, 1), (4, -1), "CENTER"),
                    ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor(f"#{_SUBTOTAL_FILL}")),
                    ("FONTNAME", (3, -1), (4, -1), "Helvetica-Bold"),
                ]
            )
        )
        story.append(table)

    if not story:
        story.append(Paragraph("No selected employees", title_style))
    doc.build(story)
    return buffer.getvalue()


def generate_timesheet_pdf(payload: AttendanceReportExportRequest) -> bytes:
    dates, employees, grouped = _build_timesheet_maps(payload)
    page_size = landscape(A3) if len(dates) > 10 else landscape(A4)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=10 * mm,
        bottomMargin=8 * mm,
    )
    styles = getSampleStyleSheet()
    story = [Paragraph(payload.title, styles["Title"])]
    if payload.periodLabel:
        story.append(Paragraph(html.escape(payload.periodLabel), styles["Normal"]))
    story.append(Spacer(1, 4 * mm))

    table_data: list[list[object]] = [
        ["Employee", "Total Hours", *[str(day.day) for day in dates]],
        ["Day:", "", *[_short_day_label(day) for day in dates]],
    ]
    for employee in employees:
        by_date = grouped.get(employee.id, {})
        values = []
        total = 0.0
        for day in dates:
            report_row = by_date.get(day)
            hours = _numeric_hours(report_row.totalHours, payload.force8) if report_row else 0.0
            total += hours
            values.append(f"{hours:.2f}" if hours else "")
        table_data.append([_employee_name(employee), f"{total:.2f}" if total else "", *values])

    usable_width = page_size[0] - 16 * mm
    employee_width = 52 * mm
    total_width = 20 * mm
    day_width = max((usable_width - employee_width - total_width) / max(len(dates), 1), 7 * mm)
    table = Table(table_data, colWidths=[employee_width, total_width, *([day_width] * len(dates))], repeatRows=2)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(f"#{_HEADER_FILL}")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor(f"#{_TITLE_FILL}")),
                ("FONTNAME", (0, 0), (-1, 1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E2EC")),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 2), (0, -1), "LEFT"),
                ("FONTNAME", (0, 2), (1, -1), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()


def generate_attendance_report_export(payload: AttendanceReportExportRequest) -> bytes:
    if payload.mode == "report":
        if payload.format == "xlsx":
            return generate_report_xlsx(payload)
        return generate_report_pdf(payload)
    if payload.format == "xlsx":
        return generate_timesheet_xlsx(payload)
    return generate_timesheet_pdf(payload)
