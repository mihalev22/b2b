import logging
import sys
import time

from sqlalchemy import inspect

from app.db.session import sync_engine

logger = logging.getLogger("app")


def main() -> int:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            with sync_engine.connect() as connection:
                if inspect(connection).has_table("jobs"):
                    logger.info("таблицы готовы")
                    return 0
        except Exception:
            pass
        time.sleep(2)
    logger.error("таблицы не появились за 120 секунд")
    return 1


if __name__ == "__main__":
    sys.exit(main())
