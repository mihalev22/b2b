import time
import uuid
from datetime import UTC, datetime

from app.core.config import get_settings
from app.core.logging import get_logger, set_job_context
from app.models.entities import Item, Job
from app.services.parser import ParserError, parse_file
from app.services.storage import upload_path
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

BATCH_SIZE = 100
ACTIVE_STATUSES = ("processing", "done")


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
                session.add_all(
                    [
                        Item(
                            job_id=job.id,
                            row_number=item.row_number,
                            raw_name=item.raw_text,
                            raw_columns=item.columns,
                        )
                        for item in chunk
                    ]
                )
                job.processed_count = min(start + BATCH_SIZE, len(raw_items))
                session.commit()
            job.parse_seconds = round(time.perf_counter() - started, 3)
            job.status = "done"
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.info("job done: total=%s, seconds=%s", job.total_count, job.parse_seconds)
            return {"job_id": str(job_id), "status": "done", "total": job.total_count}
        except Exception as exc:
            session.rollback()
            job = session.get(Job, job_id)
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            session.commit()
            logger.exception("job failed")
            return {"job_id": str(job_id), "status": "failed", "error": job.error}
