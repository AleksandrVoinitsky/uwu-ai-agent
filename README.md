# uwu-ai-agent

AI-агент для проекта [UWU](https://github.com/AleksandrVoinitsky/UWU.git) —
автоматический консультант покупателей и чат-ассистент. Отдельный сервис
(отдельный репозиторий и Docker-контейнер), который **является клиентом REST
API ядра UWU**, а не частью учётного процесса: он не пишет напрямую в БД ядра
и не дублирует его бизнес-логику.

Полная спецификация агента (архитектура, граф LangGraph, управление промптами
и действиями, персонализация, изменения БД/API, тесты) — в ядре UWU:
[`docs/ai-agent.md`](https://github.com/AleksandrVoinitsky/UWU/blob/main/docs/ai-agent.md).
Этот репозиторий реализует **исполняющую часть** (control-plane + оркестрация),
ядро остаётся единственным источником бизнес-логики и данных.

## Статус

Фаза 3 — **tool-calling**: граф LangGraph `classify_intent → decide_action ⇄
call_tool → finalize`, где LLM (Amvera) сам выбирает и вызывает read-инструменты;
промпты/инструменты загружаются из ядра. План и статус фаз — в
[`ROADMAP.md`](ROADMAP.md).

## Что делает агент (целевое состояние)

1. **Консультирует покупателей** — товары, наличие, цены, доставка, статус заказа, возвраты.
2. **Работает в чатах** — каналы ядра `internal | telegram | maks | site`.
3. **Персонализирует** — по профилю, истории покупок, корзине и спискам покупок.
4. **Выполняет действия под присмотром** — чтение авто; мутирующие ниже порога —
   авто; выше порога — одобрение оператора (human-in-the-loop).

## Архитектура

```
                 ┌──────────────────────────────┐
  Telegram/MAX/  │   UWU (ядро учёта, контейнер) │
  site-чат  ───▶ │  Chat / Message / BotManager  │
                 │  REST API + права + админка   │
                 └──────────────┬───────────────┘
                                │  REST API (API-key auth)
                                │  webhook / polling событий
                 ┌──────────────▼───────────────┐
                 │  uwu-ai-agent (этот сервис)   │
                 │  FastAPI control-plane,        │
                 │  LangGraph-оркестрация, LLM,   │
                 │  тулзы-обёртки над API ядра    │
                 └──────────────────────────────┘
```

| Аспект | Решение |
| --- | --- |
| Размещение | отдельный репозиторий + отдельный контейнер (`uwu-ai-agent`) |
| Язык | Python 3.13 (как ядро) |
| Оркестрация | **LangGraph** (state machine, checkpointer, interrupts, tools) |
| LLM | подключаемый (OpenAI-совместимый API через LangChain) |
| Аутентификация | **API-ключ** агента в ядре |
| Доступ к данным | только через REST API ядра (не прямой доступ к БД) |

## Быстрый старт

```bash
# 1. Настроить окружение
cp .env.example .env   # задать UWU_API_BASE_URL, UWU_API_KEY, LLM_API_KEY

# 2. Локально (venv)
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt        # Windows
.venv/bin/pip install -r requirements.txt            # Linux/macOS
.venv\Scripts\uvicorn app.main:app --port 8100       # Windows

# 3. Или в Docker
docker compose up --build
```

Открыть http://localhost:8100/healthz → `{"status":"ok",...}`.

## Тесты

```bash
pytest tests/ -v
```

Тесты не требуют PostgreSQL (in-memory checkpointer + ASGI-транспорт httpx).
Подробнее — [`docs/testing.md`](docs/testing.md).

## Документация

Полная документация — в каталоге [`docs/`](docs/README.md):

| Раздел | Описание |
| --- | --- |
| [architecture](docs/architecture.md) | Архитектура, стек, карта модулей |
| [graph](docs/graph.md) | Граф LangGraph: состояние, узлы, рёбра |
| [integration](docs/integration.md) | Интеграция с ядром UWU: эндпоинты, API-ключ, поток, HITL |
| [testing](docs/testing.md) | Автотесты (TDD), слои, запуск |
| [deployment](docs/deployment.md) | Сборка Docker, развёртывание, переменные окружения |

## Технологический стек

Python 3.13 · FastAPI · LangGraph · LangChain (OpenAI-совместимый API) ·
httpx (клиент ядра) · pydantic v2 / pydantic-settings · PostgreSQL (checkpointer,
фаза 2+) · pytest / pytest-asyncio · ruff / mypy · Docker Compose.

## Roadmap

План реализации по фазам — в [`ROADMAP.md`](ROADMAP.md).
