import csv
import io

from app.models.entities import Item

EXPORT_HEADER = ["№", "Наименование", "Код КТРУ", "Наименование КТРУ", "Уверенность (%)", "Статус"]


def _csv_safe(value):
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@"):
        return f"'{value}"
    return value


def _rows(items: list[Item]) -> list[list]:
    rows = [EXPORT_HEADER]
    for item in items:
        values = [
            item.row_number,
            item.raw_name,
            item.ktru_code or "",
            item.ktru_name or "",
            f"{item.confidence:.0f}" if item.confidence is not None else "",
            item.status,
        ]
        rows.append([_csv_safe(value) for value in values])
    return rows


def items_to_csv(items: list[Item]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerows(_rows(items))
    return buffer.getvalue().encode("utf-8-sig")


def items_to_xlsx(items: list[Item]) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Результат"
    for row in _rows(items):
        sheet.append(row)
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    widths = [6, 60, 24, 40, 16, 16]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
