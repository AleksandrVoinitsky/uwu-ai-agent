# Архитектура

## Технологический стек

| Слой | Технология | Обоснование |
| --- | --- | --- |
| Язык | Python 3.13 | Как ядро UWU |
| Control-plane | FastAPI | `healthz`, `webhook`, наблюдение; авто-OpenAPI |
| Оркестрация | LangGraph | state machine, checkpointer, interrupts (HITL), tools |
| LLM | LangChain (`langchain-openai`) | OpenAI-совместимый API; провайдер задаётся конфигом |
| Клиент ядра | httpx (async) | тонкие обёртки над REST API ядра |
| Checkpointer | `langgraph-checkpoint-postgres` (схема `agent`) | персистентность состояния и resume |
| Валидация | pydantic v2 / pydantic-settings | конфигурация и DTO |
| Тесты | pytest + pytest-asyncio | см. [testing](testing.md) |
| Развёртывание | Docker + Docker Compose | отдельный контейнер |

## Слоистая архитектура

```
app/
├── core/        # Конфигурация (config.py), логирование
├── clients/     # HTTP-клиенты внешних систем (uwu.py)
├── llm/         # Фабрика LLM-моделей (OpenAI-совместимый API)
├── graph/       # LangGraph: state.py, nodes.py, builder.py
└── api/         # control-plane (routes.py); main.py — точка входа
```

Направление зависимостей — строго сверху вниз:

```
api → graph → clients/core
     graph → llm
```

Узлы графа — чистые функции от состояния; они обращаются к ядру через
`UwuClient` и к LLM через фабрику `app.llm.factory`, не зная об HTTP-слое
control-plane.

## Поток обработки сообщения

1. **Входящее** — ядро уведомляет агента (webhook на `/webhook` или агент
   опрашивает `/api/agent/inbox`).
2. **Граф** — классификация намерения → контекст → (тулзы) → генерация → ответ.
3. **Ответ** — агент пишет ответ обратно в ядро (`POST /api/agent/messages`).
4. **HITL** — при необходимости создаётся `AgentApproval`, граф прерывается,
   после решения оператора — возобновляется.

Подробнее — [graph](graph.md) и [integration](integration.md).

## Модули (карта)

| Модуль | Назначение |
| --- | --- |
| [`app/core/config.py`](../app/core/config.py) | Настройки (env/.env): ядро, LLM, checkpointer |
| [`app/core/logging.py`](../app/core/logging.py) | Единый формат логов |
| [`app/clients/uwu.py`](../app/clients/uwu.py) | Клиент REST API ядра (`/api/agent/*`) |
| [`app/llm/factory.py`](../app/llm/factory.py) | Создание `ChatOpenAI` из настроек |
| [`app/graph/state.py`](../app/graph/state.py) | Состояние графа `AgentState` |
| [`app/graph/nodes.py`](../app/graph/nodes.py) | Узлы графа (фаза 1 — заглушки) |
| [`app/graph/builder.py`](../app/graph/builder.py) | Сборка графа |
| [`app/api/routes.py`](../app/api/routes.py) | Маршруты control-plane |
| [`app/main.py`](../app/main.py) | Фабрика приложения, lifespan |
