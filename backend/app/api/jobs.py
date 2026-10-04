import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger, set_job_context
from app.db.session import get_session
from app.models.entities import Item, Job
from app.schemas.job import ItemPage, JobCreated, JobOut, JobPage
from app.services.exporter import items_to_csv
from app.services.queue import enqueue_process_job
from app.services.storage import UploadTooLarge, save_upload, upload_path

logger = get_logger(__name__)
router = APIRouter(prefix="/jobs", tags=["jobs"])

ALLOWED_EXTENSIONS = {".xlsx", ".csv"}


@router.post("", status_code=202, response_model=JobCreated)
async def create_job(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> JobCreated:
    settings = get_settings()
    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Ожидается файл спецификации в формате .xlsx или .csv")

    job = Job(filename=filename, file_ext=extension)
    session.add(job)
    await session.flush()

    destination = upload_path(job)
    try:
        await save_upload(file, destination, settings.max_upload_mb * 1024 * 1024)
    except UploadTooLarge:
        destination.unlink(missing_ok=True)
        await session.rollback()
        raise HTTPException(413, f"Файл больше {settings.max_upload_mb} МБ") from None
    set_job_context(job.id)
    await session.commit()

    try:
        enqueue_process_job(job.id)
    except Exception:
        job.status = "failed"
        job.error = "Не удалось поставить задание в очередь"
        await session.commit()
        logger.exception("enqueue failed")
        raise HTTPException(503, "Очередь задач недоступна, попробуйте позже") from None

    logger.info("job created: file=%s, size_limit=%sMB", filename, settings.max_upload_mb)
    return JobCreated(job_id=job.id, status=job.status, filename=filename)


@router.get("", response_model=JobPage)
async def list_jobs(
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobPage:
    total = await session.scalar(select(func.count()).select_from(Job))
    stmt = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    jobs = (await session.scalars(stmt)).all()
    return JobPage(items=list(jobs), total=total or 0, limit=limit, offset=offset)


async def get_job_or_404(session: AsyncSession, job_id: uuid.UUID) -> Job:
    job = await session.get(Job, job_id)
    if job is None:
        raise HTTPException(404, "Задание не найдено")
    return job


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> JobOut:
    return JobOut.model_validate(await get_job_or_404(session, job_id))


@router.get("/{job_id}/items", response_model=ItemPage)
async def list_items(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: str | None = Query(default=None, max_length=32),
    min_confidence: float | None = Query(default=None, ge=0, le=100),
    q: str | None = Query(default=None, max_length=256),
) -> ItemPage:
    await get_job_or_404(session, job_id)
    filters = [Item.job_id == job_id]
    if status:
        filters.append(Item.status == status)
    if min_confidence is not None:
        filters.append(Item.confidence >= min_confidence)
    if q:
        filters.append(Item.raw_name.ilike(f"%{q}%"))
    total = await session.scalar(select(func.count()).select_from(Item).where(*filters))
    stmt = (
        select(Item)
        .where(*filters)
        .order_by(Item.row_number)
        .limit(limit)
        .offset(offset)
    )
    items = (await session.scalars(stmt)).all()
    return ItemPage(items=list(items), total=total or 0, limit=limit, offset=offset)


@router.get("/{job_id}/export")
async def export_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    format: str = Query(default="csv", pattern="^(csv)$"),
) -> Response:
    job = await get_job_or_404(session, job_id)
    stmt = select(Item).where(Item.job_id == job_id).order_by(Item.row_number)
    items = (await session.scalars(stmt)).all()
    content = items_to_csv(items)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="job_{job.id}.csv"'},
    )
