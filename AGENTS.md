# AGENTS.md

Обязательный контекст для любой нейросети (Claude, Cursor, Copilot и т. п.), которая пишет код этого репозитория.
Давай этот файл первым сообщением вместе с контрактом, которого касается задача.

## Проект

КТРУ-классификатор, кейс-чемпионат B2B-РТС, задача 5. Пользователь загружает спецификацию (xlsx, csv, pdf),
система проставляет каждой позиции код КТРУ с уверенностью, человек правит спорные позиции и выгружает результат.

Критерии приёмки, под которые пишется весь код (полный список — в условиях кейса):
- №1, 2, 4, 5 — метрики качества, замеряют владельцы ml и поиска, цифры в `docs/metrics.md`.
- №3 — 1000 позиций обрабатываются быстрее 5 минут (бюджет команды — 200 с).
- №6 — обработка через очередь задач.
- №7 — система поднимается одной командой `docker compose up --build`.

## Сервисы и владельцы

| Сервис   | Каталог     | Технологии                                   | Владелец       |
|----------|-------------|----------------------------------------------|----------------|
| frontend | `frontend/` | React, TypeScript, Vite, Ant Design, nginx   | Лёша           |
| api      | `backend/`  | Python, FastAPI, SQLAlchemy, Alembic         | Женя           |
| worker   | `backend/`  | Celery                                       | Женя           |
| ml       | `ml/`       | FastAPI, модель эмбеддингов, клиент LLM      | ИИ-инженер     |
| db       | —           | PostgreSQL 16 + pgvector                     | Инженер БД     |
| redis    | —           | Redis 7, брокер Celery                       | Архитектор     |
| инфраструктура | `docker-compose.yml`, `.github/`, `scripts/`, `docs/` | compose, CI, ADR | Артас (архитектор) |

Путь данных: файл → `api` → задание в `redis` → `worker` пакетами шлёт позиции в `ml` → результат в `db`.
Фронт ходит на тот же origin, nginx проксирует `/api/` в `api:8000`.

## Структура репозитория

```
frontend/          React SPA, Dockerfile (сборка → nginx), nginx.conf
backend/app/api/   роутеры FastAPI, префикс /api/v1
backend/app/services/  парсер файлов, экспорт, очередь, хранилище
backend/app/workers/   Celery-задачи
backend/alembic/   миграции БД
backend/tests/     pytest, без Docker (SQLite)
ml/app/            сервис ml
data/              выгрузки КТРУ — НЕ в git
docs/api/openapi.yaml  контракт API (источник правды)
docs/adr/          архитектурные решения
scripts/           e2e и служебные скрипты
```

## Контракты — менять только через ADR

Контракты: `docs/api/openapi.yaml`, схема БД (миграции Alembic), контракт `ml` (`/embed`, `/classify`).

- Не меняй контракт «попутно» в задаче про что-то другое.
- Изменение контракта = отдельный PR + файл `docs/adr/NNNN-название.md` + согласие архитектора.
- `docs/api/openapi.yaml` генерируется из кода: `python backend/scripts/export_openapi.py`.
  CI падает, если код бэкенда и файл расходятся.
- `frontend/openapi.yaml` — копия контракта, типы фронта генерируются `npm run gen:api`.
  CI падает, если копия или `schema.d.ts` устарели.
- Новые поля добавляй как необязательные, существующие не удаляй и не переименовывай.

## Соглашения по коду

Python (backend, ml):
- Python 3.14 в backend, зависимости только с фиксированной версией (`==`) в `requirements.txt`.
- Линтер `ruff` (конфиг в `backend/pyproject.toml`), длина строки 100.
- Настройки только через переменные окружения (`pydantic-settings`), без хардкода адресов и ключей.
- Ошибки пользователю — на русском, без трассировок.

TypeScript (frontend):
- Типы API только из сгенерированного `src/api/schema.d.ts`, руками не пишем.
- Запросы через клиент `src/api/client.ts` (openapi-fetch), базовый URL — `window.location.origin`.
- Тексты интерфейса — в `src/texts.ts`.
- `npm run lint` и `npm run build` должны проходить без ошибок.

Общее:
- Секреты, ключи API, дампы и модели не коммитим. Новая переменная окружения → сразу в `.env.example`.
- Не добавляй зависимость, если задачу можно решить уже подключёнными.
- Не придумывай функциональность сверх задачи.

## Git и pull request

- В `main` напрямую не пушим. Ветки `feature/*`, `fix/*`, `chore/*`.
- Одна задача — один PR — до ~400 строк изменений.
- Коммиты в стиле Conventional Commits на русском: `feat(backend): ...`, `fix(frontend): ...`, `chore(infra): ...`.
- PR вливается после зелёного CI и ревью. Изменения контрактов и `docker-compose.yml` ревьюит архитектор.
- После 28 октября в `main` попадают только исправления.

## Команды

Полный стек:
```bash
cp .env.example .env
docker compose up --build        # интерфейс http://localhost:3000, Swagger http://localhost:8000/docs
bash scripts/e2e.sh              # сквозная проверка поднятого стека
docker compose down              # остановить (данные сохраняются), -v — удалить и данные
```

Backend:
```bash
cd backend
pip install -r requirements.txt
ruff check .
python -m pytest -q
python scripts/export_openapi.py   # обновить docs/api/openapi.yaml
```

Frontend:
```bash
cd frontend
npm ci
npm run gen:api   # типы из openapi.yaml
npm run lint
npm run build
npm run dev       # с моками MSW; без моков — VITE_USE_MOCKS=false в .env.local
```

## Критерий готовности задачи

Задача готова, когда:
1. Есть тест или воспроизводимая проверка, и она проходит.
2. Код запущен в контейнере через `docker compose up --build`, а не только локально.
3. CI зелёный, контракты не нарушены.
4. Если появилась новая переменная, команда или сервис — обновлены `.env.example`, README и этот файл.
