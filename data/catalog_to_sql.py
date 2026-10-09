"""Скрипт: конвертация собранного JSON каталога в SQL-дамп для Postgres."""
import json
import sys
from pathlib import Path

INPUT = Path("data/ktru_catalog.json")
OUTPUT = Path("data/ktru_catalog.sql")

CREATE_SQL = """\\set ON_ERROR_STOP on
CREATE TABLE IF NOT EXISTS ktru_position (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    okpd2_code VARCHAR(15),
    okpd2_name TEXT,
    status VARCHAR(32) DEFAULT 'active',
    source_url TEXT,
    version_id INTEGER DEFAULT 1,
    embedding VECTOR(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ktru_code ON ktru_position(code);
CREATE INDEX IF NOT EXISTS idx_ktru_okpd2 ON ktru_position(okpd2_code);
CREATE INDEX IF NOT EXISTS idx_ktru_status ON ktru_position(status);

CREATE TABLE IF NOT EXISTS ktru_characteristic (
    id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES ktru_position(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    value TEXT,
    unit VARCHAR(50)
);

CREATE INDEX IF NOT EXISTS idx_char_position ON ktru_characteristic(position_id);
"""

INSERT_SQL = """INSERT INTO ktru_position (code, name, okpd2_code, okpd2_name, status, source_url)
VALUES ('{code}', '{name}', '{okpd2}', '{okpd2_name}', '{status}', '{url}')
ON CONFLICT (code) DO NOTHING;
"""


def escape(text):
    return text.replace("'", "''").replace("\\", "\\\\")


def main():
    if not INPUT.exists():
        print(f"Файл {INPUT} не найден")
        return 1

    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    items = list(data["items"].values())
    print(f"Конвертирую {len(items)} позиций...")

    lines = [CREATE_SQL]

    for item in items:
        code = item["code"]

        okpd2 = item.get("okpd2_code", "")
        okpd2 = okpd2.lstrip(") ").strip()
        if not okpd2 or not okpd2[0].isdigit():
            okpd2 = code.split("-")[0] if "-" in code else ""

        name = item.get("name", "")
        if "Единицы" in name:
            name = name[: name.find("Единицы")].strip()
        if not name:
            name = code

        okpd2_name = item.get("okpd2_name", "")
        okpd2_name = okpd2_name.lstrip(") ").strip()

        raw_status = item.get("status", "")
        if "Включено" in raw_status:
            status = "active"
        elif "Утратило" in raw_status:
            status = "inactive"
        else:
            status = "active" if okpd2 else "unknown"

        sql = INSERT_SQL.format(
            code=escape(code),
            name=escape(name),
            okpd2=escape(okpd2),
            okpd2_name=escape(okpd2_name),
            status=status,
            url=escape(item.get("source_url", "")),
        )
        lines.append(sql)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"SQL-дамп: {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} КБ)")
    print(f"Позиций: {len(items)}")
    active = sum(1 for i in items if "Включено" in i.get("status", ""))
    print(f"Активных: {active}")
    print(f"Неактивных: {len(items) - active}")

    by_prefix = {}
    for item in items:
        p = item.get("okpd2_code", "")[:2]
        by_prefix[p] = by_prefix.get(p, 0) + 1
    print("\nПо разделам ОКПД2:")
    for p in sorted(by_prefix):
        print(f"  {p}: {by_prefix[p]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
