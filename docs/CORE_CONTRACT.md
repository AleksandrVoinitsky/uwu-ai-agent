# Контракт ядра UWU для AI-агента

> Документ для разработчика **ядра UWU** (репозиторий `AleksandrVoinitsky/UWU`,
> рабочая папка `C:\UWU`). Описывает, что именно нужно от ядра, чтобы отдельный
> сервис `uwu-ai-agent` (этот репозиторий) мог работать как клиент его REST API.
>
> Принцип: **агент — клиент API ядра**, не пишет в БД напрямую и не дублирует
> бизнес-логику. Ядро — единственный источник данных и прав.

## 1. Аутентификация агента (API-ключ)

- Таблица `agent_api_keys` уже есть (`app/models/agent.py`): `key_hash` (SHA-256),
  `permissions` (JSONB), `enabled`, `expires_at`, `last_used_at`.
- Нужна FastAPI-зависимость (рядом с `get_current_user` в `app/core/deps.py`),
  например `get_current_agent`, которая:
  - читает `Authorization: Bearer <key>` **или** `X-Api-Key: <key>`;
  - хеширует ключ SHA-256 и ищет в `agent_api_keys` (см. `agent_service.verify_key`);
  - отклоняет (401), если ключ не найден, `enabled=false` или просрочен;
  - обновляет `last_used_at`.
- Формат ключа: `uwu_` + 43 символа url-safe base64 (`agent_service.generate_api_key`).
- **Права по умолчанию** при создании ключа в админке — `AGENT_PERMISSIONS`
  (`catalog.read`, `documents.read`, `documents.write`, `reports.read`).
  Права инструментов проверяются **ядром** по `key.permissions` (принцип
  наименьших привилегий), а не агентом.

## 2. Эндпоинты, потребляемые агентом (`/api/agent/*`)

Все — с API-key авторизацией из §1.

### 2.1 `GET /api/agent/prompts`

Возвращает активные промпты (массив объектов):

```json
[
  {
    "key": "system",
    "name": "Системный промпт",
    "description": null,
    "active_version": 1,
    "template": "Ты — ассистент магазина …",
    "variables": [],
    "model": null,
    "temperature": null,
    "max_tokens": null
  }
]
```

- `template` — текст **активной версии** (`agent_prompt_versions`), `variables` —
  список плейсхолдеров, `model`/`temperature`/`max_tokens` — переопределения.
- Агент кэширует результат и использует эти промпты (не имеет «зашитых»
  бизнес-промптов, кроме жёсткой защитной рамки).

### 2.2 `GET /api/agent/tools`

Возвращает **включённые** инструменты (массив):

```json
[
  {
    "key": "search_catalog",
    "name": "Поиск товара",
    "description": "Поиск товаров по названию/артикулу.",
    "endpoint": "/api/agent/search_catalog",
    "method": "GET",
    "params_schema": {"query": "string"},
    "permission": "catalog.read",
    "approval_policy": "auto",
    "approval_threshold_amount": null,
    "rate_limit": 60
  }
]
```

### 2.3 `GET /api/agent/inbox`

Непрочитанные входящие (polling-режим), массив:

```json
[{"message_id": 1, "chat_id": 3, "chat_name": "Иван", "channel": "telegram",
  "customer_id": null, "text": "Есть в наличии?", "created_at": "…"}]
```

### 2.4 `POST /api/agent/messages`

Публикация ответа агента. Тело:

```json
{"chat_id": 3, "text": "Да, 5 штук.", "author": "agent", "agent_run_id": null}
```

- Создаёт `Message(direction="out", author="agent", agent_run_id=…)`.
- Для каналов `telegram`/`maks` ядро доставляет ответ через `deliver_outgoing`.

### 2.5 `GET /api/agent/context/{chat_id}`

Сводка контекста покупателя:

```json
{
  "chat": {"id": 3, "name": "Иван", "channel": "site", "agent_enabled": true},
  "customer": {"id": 1, "name": "Иван"},
  "cart": [{"id": 1, "nomenklatura_id": 7, "name": "Ручка", "quantity": "2.000",
            "price": "100.00", "amount": "200.00"}],
  "history": [{"id": 1, "direction": "in", "author": "customer", "text": "…",
               "created_at": "…"}]
}
```

> ⚠️ Поля `Message.author` (`operator|agent|customer`) и `Chat.agent_enabled`
> должны существовать в модели/миграции (см. §4). Суммы — строки (Decimal).

### 2.6 `POST /api/agent/approvals` / `GET /api/agent/approvals/{id}`

Human-in-the-loop. Агент создаёт запрос одобрения:

```json
{"tool_key": "create_order", "payload": {"customer_id": 1, "items": []},
 "chat_id": 3, "customer_id": 1, "run_id": 12}
```

Статус (`pending|approved|rejected`) агент опрашивает через `GET …/{id}`:

```json
{"id": 5, "tool_key": "create_order", "status": "approved",
 "resume_value": {"approved": true}, "decided_by": "admin", "decided_at": "…"}
```

**Решение принимает оператор** в админке (`/admin/agent/approvals/{id}/decide`,
cookie-авторизация), **не** агент своим API-ключом — иначе агент смог бы
самоодобрять свои действия.

### 2.7 `POST /api/agent/runs`

Аудит запуска. Тело:

```json
{"trace_id": "…", "chat_id": 3, "customer_id": 1, "intent": "stock",
 "prompt_versions": {}, "tool_calls": [], "tokens_in": 0, "tokens_out": 0,
 "latency_ms": 0, "model": "gpt-4.1", "status": "ok", "error": null}
```

### 2.8 Tool-friendly чтение (для инструментов агента)

| Эндпоинт | Параметры | Возвращает |
| --- | --- | --- |
| `GET /api/agent/search_catalog` | `query` | `[{id, name, full_name, artikul, price, stock}]` |
| `GET /api/agent/get_stock` | `nomenklatura_id` | `{nomenklatura_id, balance, available}` |
| `GET /api/agent/get_cart` | `customer_id` | `{customer_id, items[], total}` |
| `GET /api/agent/get_zakaz` | `order_id` | контекст заявки (id, number, date, total, status, items[]) |

Чтение — `auto` (без одобрения); запись (корзина/заказ) — через существующие
`documents`/`customer` API с политикой одобрения (см. §5).

## 3. Модель данных (обязательные изменения)

В `app/models/messaging.py` + миграция:

- `Message.author` — `String(20)`, default `"operator"` (`operator|agent|customer`).
- `Message.agent_run_id` — `FK(agent_runs.id)`, nullable.
- `Chat.agent_enabled` — `Boolean`, default `false` (включать агента по чату/каналу).

## 4. Дефолтные промпты и инструменты (сид)

Агент ожидает эти ключи (создаются идемпотентно в `agent_service.seed_agent`):

- Промпты: `system`, `classify_intent`, `generate`, `reorder_suggestion`.
  Плейсхолдеры: `classify_intent` → `{messages}`; `generate` → `{customer}`,
  `{history}`, `{context}`, `{intent}`; `reorder_suggestion` → `{customer}`,
  `{history}`, `{reorder}`.
- Инструменты: `search_catalog`, `get_stock`, `get_cart`, `get_order_status`,
  `add_to_cart`, `create_order` (эндпоинты и политики одобрения — в `DEFAULT_TOOLS`).

## 5. Политики одобрения (HITL по порогу)

| Действие | Политика |
| --- | --- |
| чтение (поиск/остатки/цены/статус/корзина) | `auto` |
| `add_to_cart` | `threshold` (порог `approval_threshold_amount`) |
| `create_order` | `always` |

Пороги настраиваются в админке (`/admin/agent/tools`).

## 6. Безопасность (ожидания от ядра)

- API-ключ: хеш SHA-256, показывается один раз, отзывается из админки.
- Права инструментов проверяет **ядро** (по `key.permissions`), не агент.
- Промпт-инъекции: жёсткая неизменяемая рамка в системном промпте; ввод
  пользователя — данные, не инструкции; инъекции логируются в `agent_runs`.
- Rate limiting инструментов и входного потока (против «зацикливания» и DoS).
- Аудит: каждый `agent_runs` и каждое `agent_approvals` фиксируются.

## 7. Что понадобится ядру на следующих фазах (пока не блокирует)

- **Checkpointer** агента — PostgreSQL, **отдельная схема `agent`**
  (`langgraph-checkpoint-postgres`); используется агентом, не ядром.
- **pgvector** для RAG-поиска по каталогу/памяти покупателей (фаза 4).
- **SSE-стриминг** ответа в чат (фаза 6) — ядро доставляет поток по мере генерации.
- Права ролей `agent.manage`, `agent.prompts.manage`, `agent.tools.manage`,
  `agent.approvals.manage` (если нужна более тонкая раздача прав в админке).
