import uuid


def enqueue_process_job(job_id: uuid.UUID) -> None:
    from app.workers.tasks import process_job

    process_job.delay(str(job_id))
