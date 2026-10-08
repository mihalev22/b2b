# Backend КТРУ: шесть шагов с локальными нейросетями

TF-IDF, словари синонимов, regex-извлечение атрибутов и неподтверждённые демо-коды удалены.

## Архитектура

1. step1_text_docs.py: чтение TXT, CSV, XLSX (все листы), DOCX, PPTX, PDF;
   атрибуты извлекает текстовая модель Ollama по JSON-схеме.
2. step2_vision_images.py: vision для PNG/JPG/JPEG и сканов PDF.
3. step3_embeddings.py: нейроэмбеддинги через /api/embed без обрезания размерности.
4. step4_ktru_catalog.py: импорт проверенного снимка официального каталога.
5. step5_match.py: хранение товаров/каталога в PostgreSQL pgvector, поиск пяти кандидатов.
6. step6_confidence.py: нейросеть проверяет кандидатов, объясняет решение или отказывается.

app.py — HTTP-обвязка, не дополнительный этап. test_backend.py — тесты.

## Скачать компактные модели

```powershell
ollama pull qwen3.5:2b-q4_K_M
ollama pull embeddinggemma:300m
ollama list
```

Одна Qwen обслуживает текст, vision и проверку, EmbeddingGemma — векторы.
Размер загрузки не равен расходу RAM; скорость и точность нужно измерять на ваших
данных. Генерация thinking выключена, температура 0, нейросеть не подменяется TF-IDF.
Параметры: OLLAMA_URL, TEXT_MODEL, VISION_MODEL, EMBED_MODEL, DATABASE_URL, KTRU_CATALOG.

## Docker: одна команда из этой папки

```powershell
docker compose up --build
```

Требуется работающий Docker Desktop. Запускаются backend, Ollama и pgvector.
Модели скачиваются при СБОРКЕ образа. Первый build требует интернета и места
на диске. Для полностью офлайн жюри передайте заранее собранные образы через
`docker save` / `docker load` вместе с каталогом; build без интернета не скачает
зависимости. CPU — по умолчанию; GPU не обязателен. Одновременно один файл,
остальные запросы получают 429 (это не долговечная очередь заданий).
Пароль postgres по умолчанию только для локальной демонстрации; в развёртывании
задайте DB_PASSWORD с URL-совместимыми символами. Ollama и база не опубликованы наружу.

## Локальная Windows Ollama

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8000
```

/extract работает без PostgreSQL. /classify требует PostgreSQL с pgvector и
DATABASE_URL (по умолчанию localhost:5432). Compose-база не публикует порт на хост;
для локального Python используйте отдельную БД либо явно настройте порт Compose.

## Официальный каталог — обязательные данные

Источник: https://zakupki.gov.ru/epz/ktru/search/results.html
Подтверждённого автоматического JSON API ЕИС здесь нет. Получите разрешённую
официальную выгрузку и нормализуйте в JSON:

- корень: source_url, exported_at (YYYY-MM-DD), items;
- позиция: code (полный XX.XX.XX.XXX-XXXXXXXX), name, description,
  attributes (словарь строк), source_url (реальная HTTPS-ссылка ЕИС), active (boolean).

```powershell
python step4_ktru_catalog.py "C:\exports\official_ktru.json"
```

Результат: data/ktru_catalog.json. Проверяются схема, уникальность полных кодов,
дата и домен. Это НЕ доказывает подлинность содержимого: проверьте по ЕИС.
XML/ZIP выгрузка требует адаптера к фактической схеме; такого адаптера здесь нет.
HTML нельзя сохранить как JSON. Без снимка /classify возвращает 503, /extract доступен.
Индекс строится при первой классификации; следующие запросы используют сохранённые
вектора. После изменения модели/каталога перезапустите backend.
Поиск точный, без HNSW: скорость на полном каталоге нужно измерять.

## API

POST /extract — multipart поле file, только извлечение, без записи в БД.
POST /classify — извлечение -> вектора -> кандидаты -> нейропроверка -> запись.
GET /health — модели, каталог и индекс; /docs — интерактивная документация.

```powershell
curl.exe -F "file=@data/demo_spec.csv" http://localhost:8000/extract
curl.exe -F "file=@data/demo_spec.csv" http://localhost:8000/classify
```

Товар: name, raw_text, brand, model, quantity, unit, attributes (любые характеристики),
corrections, uncertain, source. Классификация добавляет ktru_code, ktru_name,
confidence, reason, missing_attributes, conflicts, verdict (ok/check/manual), top5.
confidence — самооценка модели, НЕ статистическая вероятность. При manual код null.
Результаты пишутся транзакционно в parsed_products, каталог в ktru_candidates.

## Ограничения

20 МБ файла, 100 МБ распакованного OOXML, 40 PDF-страниц, 300000 символов
обычного документа, 6000 символов строки, 1000 товаров. Формулы XLSX не вычисляются;
читаются сохранённые значения Excel. DOCX/PPTX: текст/таблицы, без вложенных фото
и групп фигур. Разбиение документа может терять контекст. Проверка цитаты не
проверяет каждый атрибут. Нейросеть может ошибаться, нужна ручная проверка.
Промпт ограничивает prompt injection, но не гарантирует защиту. API без авторизации,
его нельзя напрямую публиковать в интернете. PyMuPDF: AGPL/коммерческая лицензия,
проверьте совместимость проекта. Docker использует latest Ollama: зафиксируйте
digest протестированного образа перед финальной передачей жюри.

```powershell
python -m unittest -v test_backend.py
```

Тесты контрактов с заглушками не измеряют качество модели. Полный end-to-end
требует моделей, проверенного каталога и PostgreSQL. Проценты точности не обещаются.
