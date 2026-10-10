"""Статус failed у позиции и failed_count у задания (ADR 0001)."""

from sqlalchemy import select

from app.models.entities import Item, Job
from app.workers import tasks
from app.workers.tasks import run_job

CSV = "Наименование товара;Количество\nНоутбук Dell;1\nСервер стоечный;2\nКабель ПВС;3\n".encode()


def _make_job(tmp_path, factory, content=CSV):
    job = Job(filename="spec.csv", file_ext=".csv")
    with factory() as session:
        session.add(job)
        session.commit()
    (tmp_path / f"{job.id}.csv").write_bytes(content)
    return job.id


def _fail_on(monkeypatch, marker):
    original = tasks.classify_item

    def flaky(session, raw_text):
        if marker in raw_text:
            raise RuntimeError("ml недоступен")
        return original(session, raw_text)

    monkeypatch.setattr(tasks, "classify_item", flaky)


def test_failed_item_does_not_fail_job(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    _fail_on(monkeypatch, "Сервер")
    job_id = _make_job(tmp_path, sync_factory)

    result = run_job(job_id, sync_factory)

    assert result["status"] == "done"
    with sync_factory() as session:
        job = session.get(Job, job_id)
        assert job.status == "done"
        assert job.error is None
        assert job.failed_count == 1
        assert job.processed_count == 3


def test_failed_item_has_status_reason_and_no_code(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    _fail_on(monkeypatch, "Сервер")
    job_id = _make_job(tmp_path, sync_factory)
    run_job(job_id, sync_factory)

    with sync_factory() as session:
        item = session.execute(
            select(Item).where(Item.job_id == job_id, Item.raw_name.contains("Сервер"))
        ).scalar_one()
        assert item.status == "failed"
        assert item.ktru_code is None
        assert item.confidence is None
        assert item.candidates == []
        assert item.failure_reason == "Позицию не удалось классифицировать"


def test_other_items_are_classified_normally(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    _fail_on(monkeypatch, "Сервер")
    job_id = _make_job(tmp_path, sync_factory)
    run_job(job_id, sync_factory)

    with sync_factory() as session:
        laptop = session.execute(
            select(Item).where(Item.job_id == job_id, Item.raw_name.contains("Ноутбук"))
        ).scalar_one()
        assert laptop.status != "failed"
        assert laptop.ktru_code == "26.20.11.110-00000001"


def test_no_failed_items_leaves_counter_zero(sync_factory, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "uploads_dir", str(tmp_path))
    job_id = _make_job(tmp_path, sync_factory)
    run_job(job_id, sync_factory)
    with sync_factory() as session:
        job = session.get(Job, job_id)
        assert job.failed_count == 0
        assert session.execute(
            select(Item).where(Item.job_id == job_id, Item.status == "failed")
        ).first() is None
