import pytest

from app.services.parser import ParserError, parse_file, parse_rows


def test_csv_utf8_with_semicolon_and_total_row(tmp_path):
    path = tmp_path / "spec.csv"
    content = "№;Наименование;Кол-во\n1;Ноутбук Dell;1\n2;Кабель ПВС;10\n;Итого;11\n"
    path.write_bytes(content.encode("utf-8"))
    items = parse_file(path)
    assert [item.raw_text for item in items] == ["Ноутбук Dell", "Кабель ПВС"]
    assert items[0].row_number == 2
    assert items[0].columns["Кол-во"] == "1"


def test_csv_cp1251_encoding(tmp_path):
    path = tmp_path / "spec.csv"
    path.write_bytes("Наименование;Цена\nМонитор 27 дюймов;12000\n".encode("cp1251"))
    items = parse_file(path)
    assert items[0].raw_text == "Монитор 27 дюймов"
    assert items[0].columns["Цена"] == "12000"


def test_csv_comma_delimiter(tmp_path):
    path = tmp_path / "spec.csv"
    path.write_bytes("Товар,Количество\nМФУ HP,2\n".encode())
    items = parse_file(path)
    assert items[0].raw_text == "МФУ HP"
    assert items[0].columns["Количество"] == "2"


def test_header_not_on_first_row(tmp_path):
    path = tmp_path / "spec.csv"
    content = "Спецификация закупки\n\nНаименование;Ед.\nСтол офисный;шт\n"
    path.write_bytes(content.encode("utf-8"))
    items = parse_file(path)
    assert items[0].raw_text == "Стол офисный"
    assert items[0].row_number == 4


def test_xlsx_file(tmp_path):
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["№", "Наименование", "Цена"])
    sheet.append([1, "Принтер Kyocera", 8000])
    sheet.append([2, None, 1000])
    path = tmp_path / "spec.xlsx"
    workbook.save(path)
    items = parse_file(path)
    assert len(items) == 1
    assert items[0].raw_text == "Принтер Kyocera"
    assert items[0].columns["Цена"] == "8000"


def test_empty_file_raises(tmp_path):
    path = tmp_path / "spec.csv"
    path.write_bytes(b"")
    with pytest.raises(ParserError):
        parse_file(path)


def test_no_positions_raises(tmp_path):
    path = tmp_path / "spec.csv"
    path.write_bytes("Наименование;Цена\n".encode())
    with pytest.raises(ParserError):
        parse_file(path)


def test_unsupported_extension(tmp_path):
    path = tmp_path / "spec.txt"
    path.write_bytes(b"data")
    with pytest.raises(ParserError):
        parse_file(path)


def test_skip_service_rows():
    rows = [
        ["Наименование", "Кол-во"],
        ["Итого по разделу 1", "5"],
        ["Всего", "9"],
        ["Стул", "3"],
    ]
    items = parse_rows(rows)
    assert [item.raw_text for item in items] == ["Стул"]
