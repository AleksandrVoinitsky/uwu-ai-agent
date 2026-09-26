# Roadmap — план реализации uwu-ai-agent

> Рабочий план фаз. Статусы обновляются по мере реализации. Фазы и их состав
> соответствуют §14 спецификации агента в ядре UWU (`docs/ai-agent.md`).

## Легенда статусов

- ✅ готово · 🔄 в работе · ⏳ запланировано · 🧩 зависит от ядра UWU

## Фазы

| Фаза | Содержание | Статус | Зависимости | Где делается |
| --- | --- | --- | --- | --- |
| 0. Ядро | миграции `agent_*`, API-key auth, эндпоинты §9, права агента | 🔄 частично | — | **ядро UWU** |
| 1. Каркас агента | репозиторий, FastAPI control-plane, LangGraph-граф-заглушка, healthz | ✅ | 0 | этот репозиторий |
| 2. Консультация | `classify_intent` + `retrieve_context` + `generate`, чтение каталога/остатков | ⏳ | 0, 1 | этот репозиторий |
| 3. Промпты/инструменты из админки | кэш промптов/инструментов, регистрация в LLM | ⏳ | 0, 1 | этот репозиторий |
| 4. Персонализация | профиль, история, список покупок, RAG-поиск (pgvector) | ⏳ | 2 | этот репозиторий |
| 5. HITL-действия | корзина/заказ с одобрением, `AgentApproval`, interrupt/resume | ⏳ | 3 | этот репозиторий |
| 6. Стриминг и наблюдение | SSE, `agent_runs`, LangSmith/Langfuse | ⏳ | 2 | этот репозиторий |
| 7. Eval и безопасность | золотой датасет, adversarial-тесты, rate limit | ⏳ | 2–6 | этот репозиторий |

## Детали фаз

### Фаза 0 — Ядро UWU (вне этого репозитория)

Уже реализовано в ядре (плоскость управления): модели `app/models/agent.py`,
сервис `app/services/agent_service.py`, админка `app/web/agent_admin.py`,
миграция, `verify_key()` для API-аутентификации.

Осталось в ядре (🧩 зависимость для фаз 2–7):
1. Зависимость API-key аутентификации (рядом с `get_current_user`).
2. Эндпоинты, потребляемые агентом: `/api/agent/inbox`, `/api/agent/messages`,
   `/api/agent/context/{chat_id}`, `/api/agent/prompts`, `/api/agent/tools`,
   `/api/agent/approvals`, `/api/agent/runs`.
3. Tool-friendly эндпоинты чтения: `/api/agent/search_catalog`,
   `/api/agent/get_stock`, `/api/agent/get_cart`, `/api/agent/get_zakaz`.
4. Роль/принципал агента с урезанными правами.

Контракт этих эндпоинтов зафиксирован в `docs/integration.md` и в клиенте
`app/clients/uwu.py` — по нему пишутся контракт-тесты.

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

### Фазы 2–7 — следующий шаг (этот репозиторий)

Порядок работ (от общего к частному):
1. **Фаза 2**: реальные узлы `classify_intent`/`generate` (LLM из `app/llm/`),
   `retrieve_context` через `UwuClient`, ветвление по намерению в `builder.py`.
2. **Фаза 3**: кэш промптов/инструментов (`UwuClient.get_prompts/get_tools`),
   регистрация инструментов в LLM (tool-calling).
3. **Фаза 4**: персонализация + RAG (pgvector) — после реализации
   tool-friendly эндпоинтов в ядре.
4. **Фаза 5**: HITL — `request_approval`/`resume_after_approval`, interrupt,
   checkpointer PostgreSQL (схема `agent`).
5. **Фаза 6**: SSE-стриминг ответа, запись `agent_runs`.
6. **Фаза 7**: eval-набор, adversarial-тесты, rate limiting.

## Точки согласования с автором (🧩)

1. **Эндпоинты ядра `/api/agent/*`** (фаза 0, п.2–3) — реализуются в ядре UWU;
   согласовать приоритет и формат авторизации (сейчас контракт предполагает
   `Authorization: Bearer <API-key>`).
2. **LLM-провайдер** — конкретный OpenAI-совместимый бэкенд/ключ задаются
   конфигурацией (`LLM_BASE_URL`/`LLM_API_KEY`), не кодом.
3. **Топология на хостинге** — общая Docker-сеть с ядром, имя сервиса ядра в
   `UWU_API_BASE_URL` (см. `docs/deployment.md`).
