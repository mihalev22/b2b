# КТРУ-классификатор

Кейс-чемпионат B2B-РТС «AI Procurement Copilot», задача 5.
Загружаешь спецификацию (.xlsx/.csv) → система проставляет коды КТРУ с уверенностью → ручная правка → экспорт.

## Структура

```
frontend/  React SPA (Лёша)
backend/   FastAPI + Celery: api, worker (Женя)
ml/        сервис ml: эмбеддинги, извлечение атрибутов (..)
data/      выгрузки КТРУ (НЕ в git, только .gitkeep) 
docs/      контракты, ADR, метрики (..)
```

## Правила гита

1. В `main` напрямую не пушим. Работаем в ветках `feature/*`
2. Закончил задачу → Pull Request → ревью .. (через Claude) → Merge
3. PR маленькие: одна задача, ~до 400 строк
4. Merge жмёт только .. — `main` всегда рабочий

## Запуск

Полный стек (frontend, api, worker, ml, redis, db) из корня репозитория:

```bash
cp .env.example .env
docker compose up --build
```

- Интерфейс: http://localhost:3000
- API и Swagger: http://localhost:8000/docs
- `ml` пока заглушка с `/health`, контракт `/embed` и `/classify` — за ИИ-инженером

Примеры API-запросов — в `backend/README.md`.

### Заливка каталога КТРУ

Каталог (`data/ktru_full.json`) локальный, в git не лежит. Залить в БД из корня репозитория:

```bash
docker compose run --rm -e PYTHONPATH=/srv -v ./data:/data -v ./scripts/catalog:/catalog api python /catalog/load_catalog.py /data/ktru_full.json
```

Скрипт идемпотентен, запускать из контейнера (порт БД снаружи не открыт).
