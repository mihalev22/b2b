import csv
import io

from app.models.entities import Item

EXPORT_HEADER = ["№", "Наименование", "Код КТРУ", "Наименование КТРУ", "Уверенность (%)", "Статус"]


def items_to_csv(items: list[Item]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(EXPORT_HEADER)
    for item in items:
        writer.writerow(
            [
                item.row_number,
                item.raw_name,
                item.ktru_code or "",
                item.ktru_name or "",
                f"{item.confidence:.0f}" if item.confidence is not None else "",
                item.status,
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")
