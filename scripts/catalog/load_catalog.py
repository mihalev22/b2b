"""Загрузка локального JSON-каталога КТРУ в таблицу ktru_position.

Запуск (из корня репозитория, после `alembic upgrade head`):
    python scripts/catalog/load_catalog.py data/ktru_full.json

Переменная DATABASE_URL берётся из окружения или backend/.env.
Скрипт идемпотентен: существующие коды обновляются, новые добавляются.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import create_engine, text

DEFAULT_SOURCE = Path("data/ktru_full.json")
BATCH = 1000


def normalize(raw: dict) -> dict | None:
    code = (raw.get("ktru_code") or "").strip()
    name = (raw.get("name") or "").strip()
    if not code or not name:
        return None
    okpd2 = (raw.get("okpd2_code") or "").strip() or None
    return {
        "code": code[:32],
        "name": name,
        "okpd2_code": okpd2[:32] if okpd2 else None,
        "status": "active",
        "source_url": None,
    }


def main(argv: list[str]) -> int:
    source = Path(argv[1]) if len(argv) > 1 else DEFAULT_SOURCE
    if not source.exists():
        print(f"Файл не найден: {source}")
        return 1

    from app.core.config import get_settings

    data = json.loads(source.read_text(encoding="utf-8"))
    rows = [r for r in (normalize(i) for i in data["items"].values()) if r]
    print(f"Позиций к загрузке: {len(rows)}")

    engine = create_engine(get_settings().database_url.replace("+asyncpg", "+psycopg"))
    stmt = text(
        "INSERT INTO ktru_position (code, name, okpd2_code, status, source_url) "
        "VALUES (:code, :name, :okpd2_code, :status, :source_url) "
        "ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, "
        "okpd2_code = EXCLUDED.okpd2_code"
    )
    with engine.begin() as conn:
        for start in range(0, len(rows), BATCH):
            conn.execute(stmt, rows[start : start + BATCH])
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM ktru_position")).scalar()
    print(f"В таблице ktru_position: {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
