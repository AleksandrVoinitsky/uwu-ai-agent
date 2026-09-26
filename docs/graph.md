# Граф LangGraph

Оркестрация диалога — через LangGraph: state machine с checkpointer'ом и
прерываниями для human-in-the-loop. Соответствует §4 спецификации ядра
(`docs/ai-agent.md`).

## Состояние (`AgentState`)

См. [`app/graph/state.py`](../app/graph/state.py). Единая схема для всех
запусков; поля фаз 2–7 объявлены заранее.

| Поле | Тип | Назначение |
| --- | --- | --- |
| `messages` | `list[BaseMessage]` | диалог (reducer `add_messages`) |
| `chat_id` | `int \| None` | чат ядра |
| `channel` | `str` | `internal/telegram/maks/site` |
| `customer_id` | `int \| None` | покупатель (персонализация) |
| `intent` | `str \| None` | классифицированное намерение |
| `context` | `dict` | профиль, корзина, история, найденные товары |
| `tool_calls` | `list[ToolCall]` | вызванные действия |
| `pending_approval` | `ApprovalRequest \| None` | запрос одобрения (HITL) |
| `final_answer` | `str \| None` | итоговый текст |
| `run_id` / `trace_id` | `str \| None` | аудит/трассировка |

## Узлы

| Узел | Ответственность | Статус |
| --- | --- | --- |
| `classify_intent` | классификация намерения | фаза 2 (сейчас `fallback`) |
| `generate` | генерация ответа | фаза 2 (сейчас заглушка) |
| `finalize` | запись `AgentRun` | фаза 6 |
| `retrieve_context` | сбор контекста (профиль/корзина/история) | фаза 2 |
| `personalize` | персонализированный контекст | фаза 4 |
| `decide_action` / `call_tool` | выбор и выполнение действия | фазы 3, 5 |
| `request_approval` / `resume_after_approval` | HITL (interrupt/resume) | фаза 5 |

## Рёбра (текущее, фаза 1)

```
START → classify_intent → generate → finalize → END
```

Целевой граф (фазы 2–5):

```
START → classify_intent
  ├─ consultation ──────→ retrieve_context → personalize → generate → END
  ├─ read_tool (stock/price/status) → call_tool → generate → END
  └─ write_action (add_to_cart/create_order)
        → request_approval (interrupt)
        → [одобрено] → call_tool → generate → END
        → [отклонено] → generate (объяснение) → END
```

## Сборка и персистентность

- [`app/graph/builder.py`](../app/graph/builder.py) — `build_graph(checkpointer=None)`
  собирает и компилирует граф.
- Без переданного checkpointer'а используется `MemorySaver` (тесты/разработка);
  при вызове обязателен `config={"configurable": {"thread_id": ...}}`
  (thread_id = беседа).
- Production-персистентность — `langgraph-checkpoint-postgres`, схема `agent`
  (фаза 2+; см. `CHECKPOINT_DB_URL` в [deployment](deployment.md)).
