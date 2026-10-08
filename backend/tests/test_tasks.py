import uuid

from sqlalchemy import select

from app.models.entities import Correction, Item, Job
from app.workers.tasks import run_job

CSV_CONTENT = "№;Наименование\n1;Ноутбук Dell\n2;Кабель ПВС\n".encode()


def _make_job(tmp_path, factory, filename="spec.csv", content=CSV_CONTENT, ext=".csv"):
    job = Job(filename=filename, file_ext=ext)
    with factory() as session:
        session.add(job)
        session.commit()
    path = tmp_path / f"{job.id}{ext}"
    path.write_bytes(content)
    return job.id, path


def test_run_job_marks_done(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    job_id, path = _make_job(tmp_path, sync_factory)
    assert path.exists()

    result = run_job(job_id, sync_factory)
    assert result["status"] == "done"
    assert result["total"] == 2

    with sync_factory() as session:
        job = session.get(Job, job_id)
        assert job.status == "done"
        assert job.started_at is not None
        assert job.finished_at is not None
        assert job.error is None
        items = session.execute(select(Item).where(Item.job_id == job_id)).scalars().all()
        assert len(items) == 2


def test_run_job_is_idempotent(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    job_id, _ = _make_job(tmp_path, sync_factory)
    first = run_job(job_id, sync_factory)
    second = run_job(job_id, sync_factory)
    assert first["status"] == "done"
    assert second["status"] == "done"
    with sync_factory() as session:
        job = session.get(Job, job_id)
        assert job.processed_count == 2
        items = session.execute(select(Item).where(Item.job_id == job_id)).scalars().all()
        assert len(items) == 2


def test_run_job_missing_file_fails(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    job_id, path = _make_job(tmp_path, sync_factory)
    path.unlink()
    result = run_job(job_id, sync_factory)
    assert result["status"] == "failed"
    with sync_factory() as session:
        job = session.get(Job, job_id)
        assert job.status == "failed"
        assert job.error


def test_run_job_unknown_job(sync_factory):
    result = run_job(uuid.uuid4(), sync_factory)
    assert result["status"] == "not_found"


def test_run_job_too_many_positions(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "max_items", 2)
    rows = "Наименование\n" + "\n".join(f"Товар {i}" for i in range(1, 6)) + "\n"
    job_id, _ = _make_job(tmp_path, sync_factory, content=rows.encode("utf-8"))
    result = run_job(job_id, sync_factory)
    assert result["status"] == "failed"
    assert "максимум" in result["error"]


def test_correction_writes_log(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    job_id, _ = _make_job(tmp_path, sync_factory)
    run_job(job_id, sync_factory)

    with sync_factory() as session:
        db_item = session.execute(select(Item).where(Item.job_id == job_id)).scalars().first()
        db_item.ktru_code = "26.20.11.110-00000009"
        db_item.status = "corrected"
        session.add(
            Correction(
                item_id=db_item.id,
                job_id=job_id,
                old_code=None,
                new_code="26.20.11.110-00000009",
            )
        )
        session.commit()
        correction = session.execute(select(Correction)).scalars().first()
        assert correction.new_code == "26.20.11.110-00000009"
        assert correction.old_code is None
