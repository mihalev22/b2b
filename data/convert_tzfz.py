"""Конвертация полного каталога tzfz.ru в SQL для Postgres."""
import json
import sys
from pathlib import Path

INPUT = Path("data/ktru_full.json")
OUTPUT = Path("data/ktru_full.sql")

CREATE = """\\set ON_ERROR_STOP on
DROP TABLE IF EXISTS ktru_characteristic CASCADE;
DROP TABLE IF EXISTS ktru_position CASCADE;

CREATE TABLE ktru_position (
    id SERIAL PRIMARY KEY,
    code VARCHAR(32) UNIQUE NOT NULL,
    name TEXT NOT NULL,
    unit VARCHAR(50),
    okpd2_code VARCHAR(15),
    status VARCHAR(32) DEFAULT 'active',
    source VARCHAR(20) DEFAULT 'tzfz.ru',
    version_id INTEGER DEFAULT 1,
    embedding VECTOR(768),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_ktru_code ON ktru_position(code);
CREATE INDEX idx_ktru_okpd2 ON ktru_position(okpd2_code);
CREATE INDEX idx_ktru_name_trgm ON ktru_position USING gin(name gin_trgm_ops);

CREATE TABLE ktru_characteristic (
    id SERIAL PRIMARY KEY,
    position_id INTEGER REFERENCES ktru_position(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    unit VARCHAR(50),
    is_required BOOLEAN DEFAULT FALSE,
    allowed_values JSONB
);

CREATE INDEX idx_char_position ON ktru_characteristic(position_id);
"""


def esc(text):
    if text is None:
        return ""
    return str(text).replace("'", "''").replace("\\", "\\\\")


def main():
    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    items = list(data["items"].values())
    print(f"Конвертирую {len(items)} позиций...")

    lines = [CREATE]
    char_lines = []

    for item in items:
        code = esc(item.get("ktru_code", ""))
        name = esc(item.get("name", ""))
        unit = esc(item.get("unit", ""))
        okpd2 = esc(item.get("okpd2_code", ""))

        lines.append(
            f"INSERT INTO ktru_position (code, name, unit, okpd2_code) "
            f"VALUES ('{code}', '{name}', '{unit}', '{okpd2}') "
            f"ON CONFLICT (code) DO NOTHING;"
        )

        for ch in item.get("characteristics", []):
            import json as j

            allowed = j.dumps(ch.get("allowed_values", []), ensure_ascii=False)
            allowed = allowed.replace("'", "''")
            ch_name = esc(ch.get("name", ""))
            ch_unit = esc(ch.get("unit", ""))
            req = "true" if ch.get("required") else "false"
            char_lines.append(
                f"INSERT INTO ktru_characteristic (position_id, name, unit, is_required, allowed_values) "
                f"SELECT id, '{ch_name}', '{ch_unit}', {req}, '{allowed}'::jsonb "
                f"FROM ktru_position WHERE code = '{code}';"
            )

    lines.extend(char_lines)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    chars = len(char_lines)
    print(f"SQL: {OUTPUT} ({size_mb:.1f} МБ)")
    print(f"Позиций: {len(items)}")
    print(f"Характеристик: {chars}")
    print(f"Со характеристиками: {sum(1 for i in items if i.get('characteristics'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
