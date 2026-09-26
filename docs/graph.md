# Граф LangGraph

Оркестрация диалога — через LangGraph: state machine с checkpointer'ом и
прерываниями для human-in-the-loop. Соответствует §4 спецификации ядра
(`docs/ai-agent.md`).

## Состояние (`AgentState`)

См. [`app/graph/state.py`](../app/graph/state.py). Единая схема для всех
запусков; поля фаз 4+ объявлены заранее.

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

Узлы — фабрики, замыкающие [`AgentRuntime`](../app/graph/runtime.py): LLM,
промпты, инструменты (обычные + LangChain для tool-calling), настройки. Это
позволяет тестировать узлы изолированно (мок LLM/инструментов).

## Узлы (фаза 3 — реализовано)

| Узел | Ответственность | Fallback без LLM |
| --- | --- | --- |
| `classify_intent` | LLM-классификация намерения (промпт `classify_intent`) | эвристика по ключевым словам |
| `decide_action` | LLM с привязанными инструментами: ответ или `tool_calls` | детерминированный ответ (поиск/список) |
| `call_tool` | `ToolNode` — исполнение выбранных инструментов | — |
| `finalize` | извлечение `final_answer` из последнего сообщения | — |

## Рёбра (текущее, фаза 3)

```
START → classify_intent → decide_action
                             ├─ tool_calls → call_tool → decide_action (цикл)
                             └─ ответ ────→ finalize → END
```

Целевой граф (фазы 5):

```
START → classify_intent
  ├─ consultation/read ─→ decide_action ⇄ call_tool → finalize → END
  └─ write_action (add_to_cart/create_order)
        → request_approval (interrupt)
        → [одобрено] → call_tool → END
        → [отклонено] → finalize (объяснение) → END
```

## Инструменты (фаза 3 — tool-calling)

| Инструмент | Эндпоинт ядра | Право |
| --- | --- | --- |
| `search_catalog` | `GET /api/agent/search_catalog` | `catalog.read` |
| `get_stock` | `GET /api/agent/get_stock` | `catalog.read` |
| `get_cart` | `GET /api/agent/get_cart` | `catalog.read` |
| `get_order_status` | `GET /api/agent/get_zakaz` | `documents.read` |

Инструменты — `StructuredTool` с типизированной схемой аргументов
([`app/tools/langchain_tools.py`](../app/tools/langchain_tools.py)); имена/описания
берутся из реестра ядра. LLM сам выбирает инструмент и аргументы (tool-calling).
Write-инструменты (`add_to_cart`/`create_order`) подключаются на фазе HITL (5).

## Сборка и персистентность

- [`app/graph/builder.py`](../app/graph/builder.py) — `build_graph(runtime, checkpointer=None)`.
- Без checkpointer'а — `MemorySaver`; при вызове обязателен
  `config={"configurable": {"thread_id": ...}}` (thread_id = чат).
- Production-персистентность — `langgraph-checkpoint-postgres`, схема `agent`
  (фаза 5; см. `CHECKPOINT_DB_URL` в [deployment](deployment.md)).
