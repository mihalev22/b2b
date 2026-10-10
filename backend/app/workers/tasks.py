import re
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger, set_job_context
from app.models.entities import Item, Job
from app.services.parser import ParserError, parse_file
from app.services.storage import upload_path
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

BATCH_SIZE = 100
ACTIVE_STATUSES = ("processing", "done")
# Порог автопринятия согласован с фронтом и ml: 85.
# ВРЕМЕННО: классификация ниже — локальный поиск по каталогу, без ml.
# Уверенность «40 + 15 × совпадения слов» — НЕ настоящая вероятность,
# её заменит ml (Егор) через needs_review и зону из /classify.
CONFIDENCE_AUTO = 85.0
CONFIDENCE_REVIEW = 50.0
JOB_ERROR_MESSAGE = "Не удалось обработать файл. Проверьте формат и попробуйте снова."

SEARCH_SQL = text(
    "SELECT code, name FROM ktru_position "
    "WHERE lower(name) LIKE lower(:pattern) "
    "ORDER BY code LIMIT 5"
)

STOP_WORDS = {
    "и", "в", "на", "с", "для", "от", "до", "по", "из", "у", "к", "за",
    "при", "шт", "кг", "м", "мм", "см", "л", "гб", "мб",
}


def extract_keywords(raw_text: str) -> list[str]:
    words = re.findall(r"[а-яёa-z0-9]{2,}", raw_text.lower())
    return [w for w in words if w not in STOP_WORDS]


def classify_item(session, raw_text: str) -> dict:
    keywords = extract_keywords(raw_text)

    candidates = []
    seen_codes = set()
    for kw in keywords[:5]:
        rows = session.execute(SEARCH_SQL, {"pattern": f"%{kw}%"}).fetchall()
        for row in rows:
            if row[0] not in seen_codes:
                seen_codes.add(row[0])
                name_lower = row[1].lower() if row[1] else ""
                kw_overlap = sum(1 for k in keywords if k in name_lower)
                score = min(95.0, 40.0 + kw_overlap * 15.0)
                candidates.append({"code": row[0], "name": row[1], "score": score})

    candidates.sort(key=lambda c: c["score"], reverse=True)
    candidates = candidates[:5]

    if not candidates:
        return {"ktru_code": None, "ktru_name": None, "confidence": None,
                "method": "search", "status": "needs_review", "candidates": []}

    best = candidates[0]
    status = "auto" if best["score"] >= CONFIDENCE_AUTO else "needs_review"

    return {
        "ktru_code": best["code"],
        "ktru_name": best["name"],
        "confidence": round(best["score"], 1),
        "method": "search",
        "status": status,
        "candidates": [
            {"ktru_code": c["code"], "ktru_name": c["name"],
             "confidence": round(c["score"], 1)}
            for c in candidates
        ],
    }


@celery_app.task(name="jobs.process", acks_late=True)
def process_job(job_id: str) -> dict:
    from app.db.session import SyncSessionLocal

    return run_job(uuid.UUID(job_id), SyncSessionLocal)


def run_job(job_id: uuid.UUID, session_factory) -> dict:
    set_job_context(job_id)
    with session_factory() as session:
        job = session.get(Job, job_id)
        if job is None:
            logger.warning("job not found")
            return {"job_id": str(job_id), "status": "not_found"}
        if job.status in ACTIVE_STATUSES:
            return {"job_id": str(job_id), "status": job.status, "total": job.total_count}

        job.status = "processing"
        job.started_at = datetime.now(UTC)
        session.commit()
        try:
            started = time.perf_counter()
            raw_items = parse_file(upload_path(job))
            settings = get_settings()
            if len(raw_items) > settings.max_items:
                raise ParserError(
                    f"В файле {len(raw_items)} позиций, максимум — {settings.max_items}"
                )
            job.total_count = len(raw_items)
            session.commit()

            for start in range(0, len(raw_items), BATCH_SIZE):
                chunk = raw_items[start : start + BATCH_SIZE]
                for raw_item in chunk:
                    result = classify_item(session, raw_item.raw_text)
                    session.add(
                        Item(
                            job_id=job.id,
                            row_number=raw_item.row_number,
                            raw_name=raw_item.raw_text,
                            raw_columns=raw_item.columns,
                            ktru_code=result["ktru_code"],
                            ktru_name=result["ktru_name"],
                            confidence=result["confidence"],
                            method=result["method"],
                            status=result["status"],
                            candidates=result["candidates"],
                        )
                    )
                job.processed_count = min(start + BATCH_SIZE, len(raw_items))
                session.commit()

            job.parse_seconds = round(time.perf_counter() - started, 3)
            job.status = "done"
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.info("job done: total=%s, seconds=%s", job.total_count, job.parse_seconds)
            return {"job_id": str(job_id), "status": "done", "total": job.total_count}
        except ParserError as exc:
            session.rollback()
            job = session.get(Job, job_id)
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.warning("job rejected: %s", exc)
            return {"job_id": str(job_id), "status": "failed", "error": job.error}
        except Exception:
            session.rollback()
            job = session.get(Job, job_id)
            job.status = "failed"
            job.error = JOB_ERROR_MESSAGE
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.exception("job failed: job_id=%s", job_id)
            return {"job_id": str(job_id), "status": "failed", "error": job.error}
