# RAG-агент для юридических документов (RU)

Цель: помощник для российских компаний без внутреннего юриста. Агент читает и индексирует документы, выполняет поиск и отвечает на вопросы на русском языке, используя устойчивую многошаговую стратегию.

## Архитектура
- Источники данных: `ParsedDocument` и их `DocumentChunk` (Postgres). Вектора фрагментов — Qdrant.
- Индексация: `DocumentUploadPipeline` → `DocumentParser` (pdfminer.six / python-docx / python-pptx / plaintext fallback) → `ChunkSplitter` (Markdown-aware RecursiveCharacterTextSplitter) → сохранение чанков → `DocumentVectorManager` (OpenRouter embeddings → Qdrant).
- Поиск: `DocumentVectorManager.search_chunks` с фильтрами по `user_id` и списку `document_id` (опционально) и порогом сходства.
- LLM: OpenRouter Chat API (OpenAI-совместимый). Клиент — `OpenRouterChatClient`.
- Агент: `RagAgent` orchestrator — сценарный выбор, Fusion RAG (уточнение/разбиение вопросов), извлечение контекста и генерация ответа.

Директории:
- `services/rag/`
  - `agent.py` — оркестрация сценариев
  - `openrouter_chat.py` — клиент чата OpenRouter
  - `prompt_storage/` — русские шаблоны подсказок (system/orchestrator/fusion)

## Сценарии
1) Поиск документа: документов не выбрано, пользователь формулирует запрос типа «найти документ/пункт/тип договора». Действия: vector search по всем документам пользователя → ответ с цитатами чанков.
2) Выбраны несколько документов:
   - Если общий объём < 50k символов — прямое использование полного контекста;
   - Иначе — RAG по выбранным `document_id`.
3) Документы не выбраны и непонятно, что искать — агент запрашивает уточнения.
4) Общая беседа — использовать последние N сообщений (по умолчанию 20) без поиска.

Выбор сценария выполняется через промпт `orchestrator_ru.txt` (LLM-классификация) с минимальным JSON-результатом.

## Fusion RAG
- Переформулировки и подзапросы: `fusion_ru.txt` генерирует 1–2 уточнения и 2–5 под-вопросов для поиска.
- Слияние: после получения релевантных фрагментов агент синтезирует ответ (резюме → правовой анализ → выдержки/цитаты с контекстом).

## Порог сходства и топ-K
- `DocumentVectorManager.search_chunks` принимает `score_threshold` (например, 0.7) и `limit` (по умолчанию 8). Qdrant фильтруется по `user_id` и опциональным `document_id`. Порог отсеивает слабые совпадения.

## Контекст чата
- Репозиторий `MessageRepository.get_last_for_chat` возвращает последние N сообщений, которые агент добавляет к подсказкам (деловой стиль, русский язык, отсутствие галлюцинаций).

## Промпты (RU)
- `system_ru.txt`: роль ассистента, стиль, ограничения, требования на язык.
- `orchestrator_ru.txt`: схема принятия сценария (1–4) и формат JSON-ответа.
- `fusion_ru.txt`: формат уточнений/подзапросов и структура синтеза.

## Вызов функций (расширяемо)
- Агент может вызывать внутренние функции, такие как `search_document_chunks` или загрузка полных текстов. Сегодня реализован прямой вызов поиска из кода; при необходимости можно добавить параметры `tools` к OpenRouter Chat API и обрабатывать `tool_calls`.

## Конфигурация
- OpenRouter: `OPENROUTER_API_KEY`, `OPENROUTER_CHAT_MODEL`, `OPENROUTER_CHAT_URL`, `OPENROUTER_CHAT_TIMEOUT_SECONDS`.
- Векторка/индексация: см. `documentation/vector_pipeline.md` (OpenRouter embeddings, Qdrant, MinIO для хранения исходных файлов).

## Потоки
1) Upload: файл → MinIO URL → `DocumentParser` (PDF → pdfminer, DOCX → python-docx, PPTX → python-pptx, остальные → текстовый декодер) → Split → DB → Embeddings → Qdrant.
2) Query: `RagAgent.run` → выбор сценария → (опционально Fusion) → поиск/контекст → ответ на русском.

## Корпоративная база знаний (`knowledge_base_chunks`)
- Отдельная коллекция Qdrant c `payload.source = "knowledge_base"` и `user_id=0`, куда попадает ETL из `knowledge_base/train_data.csv`.
- Используем embeddings `qwen/qwen3-embedding-8b` (размерность 4096); RAG-ответы строим при сценарии 2 (общие вопросы) через функцию `search_general_kb`.

### Инструкции по обслуживанию коллекции
1. **Ингест / переиндексация**  
   ```
   cd backend
   PYTHONPATH=src poetry run python ../knowledge_base/kb_etl.py --reset-collection
   ```  
   Скрипт дропает и пересоздаёт коллекцию перед загрузкой, чтобы гарантировать корректную размерность вектора. Без флага `--reset-collection` можно запускать инкрементально.
2. **Смена embedding-модели**  
   При обновлении модели всегда выполняем прогон с `--reset-collection`, иначе Qdrant вернёт ошибку `Wrong input: Vector dimension error (expected 3072, got 4096)` и т.п.
3. **Поисковый слой**  
   - `search_general_kb` использует `DocumentVectorManager`, сконфигурированный на коллекцию `knowledge_base_chunks`, и накладывает фильтр `source="knowledge_base"`.  
   - Ответы в RAG указывают источник («Внутренняя база знаний») и приоритизируют эти чанки, если пользователь не предоставил собственных документов.
4. **Отладка**  
   - Для тестового запуска используем `--limit N` и `--dry-run` в `kb_etl.py`.  
   - Логи `structlog` (`qdrant-upsert-success`, `qdrant-collection-created`) подтверждают, что коллекция пересоздана и загружена корректно.

## Ограничения и дальнейшие шаги
- Добавить полноценно управляемые функции (tools) и внешние API-колбеки.
- Улучшить детектор сценариев (правила + LLM-верификация).
- Добавить ранжирование фрагментов с перефразированием запроса (query expansion).
- Кэшировать результаты поиска и короткие ответы по документам.


## Улучшения
- Детектор сценариев: сначала правила, затем LLM-верификация с полем confidence; при низкой уверенности используется rule_guess.
- Query Expansion: модуль Fusion генерирует refinements/subqueries; поиск выполняется по всем вариантам, результаты объединяются Reciprocal Rank Fusion (RRF).
- Порог сходства: управляется параметром `score_threshold`; топ-K — параметр агента.
- Генерация: управляемые параметры OpenRouter (temperature/top_p/penalties, JSON-ответы в критичных шагах).
- Ответы строятся в Markdown с секциями «Краткий вывод / Подробный анализ / Источники» и ссылками вида [[Источник: …]].
- Промпты: значительно усилены инструкции system/orchestrator/fusion (см. `services/rag/prompt_storage`).
