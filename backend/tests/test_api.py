import uuid

from conftest import CSV_CONTENT


async def test_health(client):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert {component["name"] for component in body["components"]} == {"postgres", "redis"}


async def test_upload_rejects_wrong_extension(client):
    response = await client.post(
        "/api/v1/jobs",
        files={"file": ("doc.txt", b"data", "text/plain")},
    )
    assert response.status_code == 415
    assert "xlsx" in response.json()["detail"]


async def test_upload_rejects_too_big_file(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    response = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", b"x" * 1024, "text/csv")},
    )
    assert response.status_code == 413


async def test_unknown_job_returns_404(client):
    import uuid

    response = await client.get(f"/api/v1/jobs/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_full_flow_upload_status_items_correction_export(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    assert upload.status_code == 202
    job_id = upload.json()["job_id"]
    assert upload.json()["status"] == "queued"

    status = await client.get(f"/api/v1/jobs/{job_id}")
    assert status.status_code == 200
    body = status.json()
    assert body["status"] == "done"
    assert body["total_count"] == 2
    assert body["processed_count"] == 2
    assert body["parse_seconds"] is not None

    items = await client.get(f"/api/v1/jobs/{job_id}/items")
    assert items.status_code == 200
    page = items.json()
    assert page["total"] == 2
    raw_names = {item["raw_name"] for item in page["items"]}
    assert raw_names == {"Ноутбук Dell Latitude 5540", "Кабель ПВС 3х1.5"}
    assert page["items"][0]["status"] in ("pending", "needs_review", "auto")
    assert isinstance(page["items"][0]["candidates"], list)

    filtered = await client.get(f"/api/v1/jobs/{job_id}/items", params={"q": "Кабель"})
    assert filtered.json()["total"] == 1
    assert filtered.json()["items"][0]["raw_name"] == "Кабель ПВС 3х1.5"

    item_id = page["items"][0]["id"]
    patch = await client.patch(
        f"/api/v1/items/{item_id}",
        json={
            "ktru_code": "26.20.11.110-00000009",
            "ktru_name": "Машины вычислительные портативные",
        },
    )
    assert patch.status_code == 200
    patched = patch.json()
    assert patched["ktru_code"] == "26.20.11.110-00000009"
    assert patched["status"] == "corrected"
    assert patched["method"] == "manual"

    job_status = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_status.json()["corrected_count"] == 1

    export = await client.get(f"/api/v1/jobs/{job_id}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    text = export.content.decode("utf-8-sig")
    assert "Ноутбук Dell Latitude 5540" in text
    assert "26.20.11.110-00000009" in text

    jobs_list = await client.get("/api/v1/jobs")
    assert jobs_list.status_code == 200
    assert jobs_list.json()["total"] >= 1


async def test_accept_and_revert(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]
    items = (await client.get(f"/api/v1/jobs/{job_id}/items")).json()["items"]
    item_id = items[0]["id"]

    accept = await client.post(f"/api/v1/items/{item_id}/accept")
    assert accept.status_code in (200, 409)

    patch = await client.patch(
        f"/api/v1/items/{item_id}",
        json={"ktru_code": "26.20.11.110-00000009"},
    )
    assert patch.json()["status"] == "corrected"

    accept = await client.post(f"/api/v1/items/{item_id}/accept")
    assert accept.status_code == 200
    assert accept.json()["status"] == "accepted"

    revert = await client.post(f"/api/v1/items/{item_id}/revert")
    assert revert.status_code == 200
    reverted = revert.json()
    assert reverted["status"] in ("pending", "needs_review", "auto", "accepted")

    revert_again = await client.post(f"/api/v1/items/{item_id}/revert")
    assert revert_again.status_code == 409


async def test_bulk_accept(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]

    from sqlalchemy import update

    from app.db import session as db_session
    from app.models.entities import Item

    async with db_session.AsyncSessionLocal() as session:
        await session.execute(
            update(Item)
            .where(Item.job_id == uuid.UUID(job_id))
            .values(confidence=90.0, status="auto")
        )
        await session.commit()

    bulk = await client.post(f"/api/v1/jobs/{job_id}/accept", json={"min_confidence": 85})
    assert bulk.status_code == 200
    assert bulk.json()["accepted_count"] == 2

    job_status = await client.get(f"/api/v1/jobs/{job_id}")
    assert job_status.json()["auto_count"] == 0

    items = await client.get(f"/api/v1/jobs/{job_id}/items", params={"status": "accepted"})
    assert items.json()["total"] == 2


async def test_items_sorting_and_filters(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]

    page = await client.get(f"/api/v1/jobs/{job_id}/items", params={"limit": 1})
    assert len(page.json()["items"]) == 1
    assert page.json()["total"] == 2
    assert page.json()["limit"] == 1

    sorted_desc = await client.get(
        f"/api/v1/jobs/{job_id}/items",
        params={"sort_by": "row_number", "sort_order": "desc", "limit": 1},
    )
    assert sorted_desc.json()["items"][0]["raw_name"] == "Кабель ПВС 3х1.5"

    filtered = await client.get(
        f"/api/v1/jobs/{job_id}/items",
        params={"min_confidence": 50},
    )
    assert filtered.json()["total"] == 0


async def test_xlsx_export(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]
    export = await client.get(f"/api/v1/jobs/{job_id}/export", params={"format": "xlsx"})
    assert export.status_code == 200
    assert "spreadsheetml" in export.headers["content-type"]
    assert export.content[:2] == b"PK"


async def test_upload_rejects_fake_xlsx(client):
    response = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.xlsx", b"not a zip archive", "application/octet-stream")},
    )
    assert response.status_code == 422
    assert "xlsx" in response.json()["detail"]


async def test_csv_export_escapes_formula_injection(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]
    items = (await client.get(f"/api/v1/jobs/{job_id}/items")).json()["items"]
    item_id = items[0]["id"]
    await client.patch(
        f"/api/v1/items/{item_id}",
        json={"ktru_code": "=HYPERLINK(\"http://evil\")", "ktru_name": "=SUM(1+1)"},
    )
    export = await client.get(f"/api/v1/jobs/{job_id}/export")
    text = export.content.decode("utf-8-sig")
    assert "'=HYPERLINK" in text
    assert "'=SUM" in text


async def test_patch_unknown_item_returns_404(client):
    import uuid

    response = await client.patch(
        f"/api/v1/items/{uuid.uuid4()}",
        json={"ktru_code": "26.20.11.110-00000009"},
    )
    assert response.status_code == 404


async def test_ktru_search_works(client):
    response = await client.get("/api/v1/ktru/search", params={"q": "ноут"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] >= 0
    assert isinstance(body["items"], list)


async def test_ktru_position_not_found(client):
    response = await client.get("/api/v1/ktru/99.99.99.999-99999999")
    assert response.status_code == 404

