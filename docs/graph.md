# Граф LangGraph

Оркестрация диалога — через LangGraph: state machine с checkpointer'ом и
прерываниями для human-in-the-loop. Соответствует §4 спецификации ядра
(`docs/ai-agent.md`).

## Состояние (`AgentState`)

См. [`app/graph/state.py`](../app/graph/state.py). Единая схема для всех
запусков; поля фаз 3+ объявлены заранее.

| Поле | Тип | Назначение |
| --- | --- | --- |
| `messages` | `list[BaseMessage]` | диалог (reducer `add_messages`) |
| `chat_id` | `int \| None` | чат ядра |
| `channel` | `str` | `internal/telegram/maks/site` |
| `customer_id` | `int \| None` | покупатель (персонализация) |
| `intent` | `str \| None` | классифицированное намерение |
| `context` | `dict` | собранные данные (товары/заказ/флаг одобрения) |
| `tool_calls` | `list[ToolCall]` | вызванные действия |
| `pending_approval` | `ApprovalRequest \| None` | запрос одобрения (HITL) |
| `final_answer` | `str \| None` | итоговый текст |
| `run_id` / `trace_id` | `str \| None` | аудит/трассировка |

## Рантайм (`AgentRuntime`)

Узлы — фабрики, замыкающие [`AgentRuntime`](../app/graph/runtime.py) (LLM,
промпты, инструменты, настройки). Это позволяет тестировать узлы изолированно
(мок LLM/инструментов) и переиспользовать один граф с разными провайдерами.

## Узлы (фаза 2 — реализовано)

| Узел | Ответственность | Fallback без LLM |
| --- | --- | --- |
| `classify_intent` | LLM-классификация намерения (промпт `classify_intent`) | эвристика по ключевым словам |
| `retrieve_context` | вызов read-инструментов по намерению (поиск/остатки/заказ) | инструменты не вызываются |
| `generate` | генерация ответа (промпт `generate`/`reorder_suggestion`) | детерминированный список товаров |

`classify_intent` → `retrieve_context` → `generate` (см.
[`app/graph/nodes.py`](../app/graph/nodes.py)).

## Рёбра (текущее, фаза 2)

```
START → classify_intent → retrieve_context → generate → END
```

Целевой граф (фазы 3–5):

```
START → classify_intent
  ├─ consultation ──────→ retrieve_context → personalize → generate → END
  ├─ read_tool (stock/price/status) → call_tool → generate → END
  └─ write_action (add_to_cart/create_order)
        → request_approval (interrupt)
        → [одобрено] → call_tool → generate → END
        → [отклонено] → generate (объяснение) → END
```

## Инструменты (фаза 2 — read)

| Инструмент | Эндпоинт ядра | Намерение |
| --- | --- | --- |
| `search_catalog` | `GET /api/agent/search_catalog` | consultation/stock/price/reorder |
| `get_stock` | `GET /api/agent/get_stock` | stock |
| `get_cart` | `GET /api/agent/get_cart` | cart |
| `get_order_status` | `GET /api/agent/get_zakaz` | order_status |

Инструменты — тонкие обёртки над REST API ядра ([`app/tools/uwu_tools.py`](../app/tools/uwu_tools.py)).
Выбор инструмента сейчас детерминирован по намерению; фаза 3 — tool-calling
(LLM сам выбирает инструмент и аргументы).

## Сборка и персистентность

- [`app/graph/builder.py`](../app/graph/builder.py) — `build_graph(runtime, checkpointer=None)`.
- Без checkpointer'а — `MemorySaver`; при вызове обязателен
  `config={"configurable": {"thread_id": ...}}` (thread_id = чат).
- Production-персистентность — `langgraph-checkpoint-postgres`, схема `agent`
  (фаза 5; см. `CHECKPOINT_DB_URL` в [deployment](deployment.md)).
