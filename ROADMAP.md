# Roadmap — план реализации uwu-ai-agent

> Рабочий план фаз. Статусы обновляются по мере реализации. Фазы и их состав
> соответствуют §14 спецификации агента в ядре UWU (`docs/ai-agent.md`).

## Легенда статусов

- ✅ готово · 🔄 в работе · ⏳ запланировано · 🧩 зависит от ядра UWU

## Фазы

| Фаза | Содержание | Статус | Зависимости | Где делается |
| --- | --- | --- | --- | --- |
| 0. Ядро | миграции `agent_*`, API-key auth, эндпоинты §9, права агента | ✅ | — | **ядро UWU** |
| 1. Каркас агента | репозиторий, FastAPI control-plane, LangGraph-граф-заглушка, healthz | ✅ | 0 | этот репозиторий |
| 2. Консультация | `classify_intent` + `retrieve_context` + `generate`, чтение каталога/остатков | ✅ | 0, 1 | этот репозиторий |
| 3. Промпты/инструменты из админки | кэш промптов/инструментов, регистрация в LLM (tool-calling) | ✅ | 0, 1 | этот репозиторий |
| 4. Персонализация | профиль, история, список покупок, RAG-поиск (pgvector) | 🧩 контракт ✅ / ждёт ядро+pgvector | 2 | ядро + этот репозиторий |
| 5. HITL-действия | корзина/заказ с одобрением, `AgentApproval`, interrupt/resume | ✅ | 3 | этот репозиторий |
| 6. Стриминг и наблюдение | SSE, `agent_runs`, LangSmith/Langfuse | ✅ (SSE + аудит) | 2 | этот репозиторий |
| 7. Eval и безопасность | золотой датасет, adversarial-тесты, rate limit | ⏳ | 2–6 | этот репозиторий |

## Детали фаз

### Фаза 0 — Ядро UWU (вне этого репозитория) — ✅ готово

Реализовано в ядре UWU:
- Плоскость управления: модели `app/models/agent.py`, сервис
  `app/services/agent_service.py`, админка `app/web/agent_admin.py`, миграция.
- **API-key аутентификация**: зависимость `get_current_agent` (`app/core/deps.py`).
- **Эндпоинты, потребляемые агентом**: `app/api/agent.py` — `/api/agent/{inbox,
  messages, context, prompts, tools, approvals, runs}`.
- **Tool-friendly чтение**: `search_catalog`, `get_stock`, `get_cart`, `get_zakaz`.
- **Поля обмена**: `Message.author`/`agent_run_id`, `Chat.agent_enabled`
  (миграция `a1b2c3d4e5f9`).

Роль/принципал агента с урезанными правами представлен правами API-ключа
(`AGENT_PERMISSIONS`, выдаются по умолчанию при создании ключа в админке).

Контракт зафиксирован в `docs/integration.md` и клиенте `app/clients/uwu.py`.

### Фаза 1 — Каркас агента (✅ текущий коммит)

- Репозиторий, `.gitignore`/`.gitattributes`/`.dockerignore`/`.env.example`.
- `pyproject.toml` + `requirements.txt` (зависимости закреплены).
- FastAPI control-plane: `app/main.py`, `app/api/routes.py` (`/healthz`, `/webhook`).
- Граф LangGraph: `app/graph/{state,nodes,builder}.py` (линейная заглушка).
- Клиент ядра: `app/clients/uwu.py` (контракт `/api/agent/*`).
- Фабрика LLM: `app/llm/factory.py`.
- Docker: `Dockerfile`, `docker-compose.yml`, `entrypoint.sh`.
- Тесты: `tests/` (healthz, config, graph, client, factory).
- Документация: `README.md`, `AGENTS.md`, `ROADMAP.md`, `docs/*`.

### Фаза 2 — Консультация ✅ (реализовано)

- Реальные узлы `classify_intent`/`retrieve_context`/`generate` (`app/graph/nodes.py`)
  с LLM (Amvera, `app/llm/`) и детерминированным fallback без LLM.
- Инструменты-обёртки над ядром (`app/tools/uwu_tools.py`): `search_catalog`,
  `get_stock`, `get_cart`, `get_order_status`.
- Конфиг-лоадер промптов/инструментов из ядра с fallback (`app/config_loader/`).
- Обработка сообщений через `/webhook` + отладочный `/run` (`app/service.py`,
  `app/api/routes.py`).

### Фаза 3 — Tool-calling ✅ (реализовано)

- Инструменты чтения как LangChain `StructuredTool` с типизированной схемой
  (`app/tools/langchain_tools.py`).
- Граф `classify_intent → decide_action ⇄ call_tool → finalize` (`app/graph/`):
  LLM с привязанными инструментами сам выбирает и вызывает их (`ToolNode`).
- Кэш промптов/инструментов из ядра (`app/config_loader/`) с fallback.

### Фаза 5 — HITL ✅ (реализовано)

- Write-инструменты `add_to_cart`/`create_order` (регистрируются в LLM, но не
  исполняются напрямую).
- Узел `request_approval`: создаёт `AgentApproval` (`POST /api/agent/approvals`)
  и прерывает граф (`interrupt`); после решения оператора — выполняет write
  (`/api/agent/add_to_cart`, `/api/agent/create_order`) или формирует отказ.
- Оркестратор распознаёт прерывание (`approval_pending`) и `resume_graph` +
  эндпоинт `/resume` для возобновления.

### Фаза 6 — Стриминг и наблюдение ✅ (реализовано)

- SSE-стриминг ответа: `stream_message` + эндпоинт `POST /stream` (см.
  [`app/service.py`](../app/service.py), [`app/api/routes.py`](../app/api/routes.py)).
- Аудит запусков: запись `agent_runs` в ядро (fire-and-forget).

### Фаза 7 — Eval и безопасность ✅ (реализовано)

- Золотой датасет намерений `data/golden_dataset.json` + eval-тесты.
- Тесты безопасности: жёсткая рамка системного промпта, защита от инъекций.

### Фаза 4 — Персонализация + RAG 🧩 (ждёт ядро + pgvector)

Контракт для ядра — в [CORE_CONTRACT.md](CORE_CONTRACT.md) §7: векторный поиск
по каталогу (pgvector) и эндпоинт истории/рекомендаций. Со стороны агента —
потребление этих эндпоинтов (клиент + память покупателя).

## Точки согласования с автором (🧩)

1. **Эндпоинты ядра `/api/agent/*`** (фаза 0, п.2–3) — реализуются в ядре UWU;
   согласовать приоритет и формат авторизации (сейчас контракт предполагает
   `Authorization: Bearer <API-key>`).
2. **LLM-провайдер** — конкретный OpenAI-совместимый бэкенд/ключ задаются
   конфигурацией (`LLM_BASE_URL`/`LLM_API_KEY`), не кодом.
3. **Топология на хостинге** — общая Docker-сеть с ядром, имя сервиса ядра в
   `UWU_API_BASE_URL` (см. `docs/deployment.md`).
