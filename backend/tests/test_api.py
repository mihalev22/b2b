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
    assert page["items"][0]["status"] == "pending"

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

    corrected = await client.get(
        f"/api/v1/jobs/{job_id}/items", params={"status": "corrected"}
    )
    assert corrected.json()["total"] == 1

    export = await client.get(f"/api/v1/jobs/{job_id}/export")
    assert export.status_code == 200
    assert export.headers["content-type"].startswith("text/csv")
    text = export.content.decode("utf-8-sig")
    assert "Ноутбук Dell Latitude 5540" in text
    assert "26.20.11.110-00000009" in text

    jobs_list = await client.get("/api/v1/jobs")
    assert jobs_list.status_code == 200
    assert jobs_list.json()["total"] >= 1


async def test_items_pagination(client):
    upload = await client.post(
        "/api/v1/jobs",
        files={"file": ("spec.csv", CSV_CONTENT, "text/csv")},
    )
    job_id = upload.json()["job_id"]
    page = await client.get(f"/api/v1/jobs/{job_id}/items", params={"limit": 1})
    body = page.json()
    assert len(body["items"]) == 1
    assert body["total"] == 2
    assert body["limit"] == 1


async def test_patch_unknown_item_returns_404(client):
    import uuid

    response = await client.patch(
        f"/api/v1/items/{uuid.uuid4()}",
        json={"ktru_code": "26.20.11.110-00000009"},
    )
    assert response.status_code == 404


async def test_ktru_search_returns_501(client):
    response = await client.get("/api/v1/ktru/search", params={"q": "ноутбук"})
    assert response.status_code == 501
