# backend

FastAPI + Celery: сервисы `api` и `worker`. Владелец: Женя.

## Запуск через Docker (4 сервиса: api, worker, redis, postgres)

```bash
cd backend
docker-compose up --build
```

- API: http://localhost:8000, Swagger: http://localhost:8000/docs
- Миграции применяются автоматически перед стартом api
- Воркер ждёт готовности таблиц, затем стартует

## Запуск локально

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
.venv/Scripts/python -m pytest tests
.venv/Scripts/python -m uvicorn app.main:app --reload
```

Нужны доступные PostgreSQL и Redis, адреса задаются в `.env` (см. `.env.example` в корне репозитория).

## Тесты

```bash
.venv/Scripts/python -m pytest tests -q
```

Тесты не требуют Docker: используется общий SQLite-файл для async (API) и sync (воркер) сессий, полный цикл загрузка → очередь → обработка → правка → экспорт.

## Примеры API-запросов

```bash
# проверка живости (postgres + redis)
curl http://localhost:8000/api/v1/health

# загрузка спецификации
curl -F "file=@spec.csv" http://localhost:8000/api/v1/jobs
# → 202 {"job_id": "...", "status": "queued", "filename": "spec.csv"}

# статус задания
curl http://localhost:8000/api/v1/jobs/<job_id>

# позиции с фильтрами
curl "http://localhost:8000/api/v1/jobs/<job_id>/items?limit=50&status=corrected&q=кабель"

# ручная правка кода
curl -X PATCH http://localhost:8000/api/v1/items/<item_id> \
  -H "Content-Type: application/json" \
  -d '{"ktru_code": "26.20.11.110-00000009"}'

# экспорт результата
curl -OJ "http://localhost:8000/api/v1/jobs/<job_id>/export"
```

## Контракт

`docs/api/openapi.yaml` в корне репозитория генерируется из кода:

```bash
cd backend
.venv/Scripts/python scripts/export_openapi.py
```

Контракт меняется только через ADR (см. AGENTS.md).

## Структура

```
app/
  api/        роуты: health, jobs, items, catalog
  core/       конфиг (.env), JSON-логи с job_id
  db/         async-сессия для api, sync для воркера
  models/     jobs, items, corrections (SQLAlchemy 2.0)
  schemas/    pydantic-схемы ответов
  services/   парсер xlsx/csv, хранение файлов, экспорт, очередь
  workers/    Celery: задача jobs.process
alembic/      миграции
tests/        pytest: парсер, API e2e, воркер
```

## Статусы

- job: `queued → processing → done | failed`
- item: `pending` → (`auto` | `needs_review`) → `corrected`

## Дальше (по плану)

- мок-сервер для фронта (08.10)
- конвейер с пакетами по 50 позиций, повторы с паузой (неделя 2)
- подключение ml-сервиса по контракту (15.10)
- поиск по каталогу КТРУ поверх модуля инженера БД (20.10)
