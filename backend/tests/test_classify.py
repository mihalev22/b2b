from app.workers.tasks import classify_item


async def test_search_returns_exact_position(client):
    response = await client.get("/api/v1/ktru/search", params={"q": "Сервер"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["ktru_code"] == "26.20.14.000-00000001"
    assert body["items"][0]["ktru_name"] == "Сервер стоечный"


async def test_search_escapes_wildcards(client):
    response = await client.get("/api/v1/ktru/search", params={"q": "%%"})
    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_position_card_by_code(client):
    response = await client.get("/api/v1/ktru/26.20.11.110-00000002")
    assert response.status_code == 200
    assert response.json()["ktru_name"] == "Планшетный компьютер"


def test_classify_known_position_returns_exact_code(sync_factory):
    with sync_factory() as session:
        result = classify_item(session, "Ноутбук Dell Latitude 5540")
    assert result["ktru_code"] == "26.20.11.110-00000001"
    assert result["ktru_name"] == "Ноутбук"
    assert result["method"] == "search"
    assert result["confidence"] is not None
    assert result["confidence"] < 85.0
    assert result["status"] == "needs_review"


def test_classify_unknown_position_has_no_candidates(sync_factory):
    with sync_factory() as session:
        result = classify_item(session, "Абракадабра Квазар")
    assert result["ktru_code"] is None
    assert result["status"] == "needs_review"
    assert result["candidates"] == []


def test_classify_keeps_cyrillic_case_insensitive(sync_factory):
    with sync_factory() as session:
        result = classify_item(session, "НОУТБУК DELL")
    assert result["ktru_code"] == "26.20.11.110-00000001"
