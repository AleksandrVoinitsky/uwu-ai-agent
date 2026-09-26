# Развёртывание (Docker)

## Состав

`docker-compose.yml` поднимает один сервис:

1. **agent** — uwu-ai-agent (FastAPI + uvicorn), порт 8100.

Checkpointer PostgreSQL (схема `agent`) подключается на фазе 2+ через
`CHECKPOINT_DB_URL`; ядро UWU разворачивается отдельно (свой compose) в общей
Docker-сети.

## Переменные окружения

Задаются в `.env` (см. [`.env.example`](../.env.example)):

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `ENVIRONMENT` | `production` | окружение (fail-fast проверки) |
| `AGENT_PORT` | `8100` | порт control-plane |
| `LOG_LEVEL` | `INFO` | уровень логирования |
| `UWU_API_BASE_URL` | `http://localhost:8000` | базовый URL ядра UWU |
| `UWU_API_KEY` | — | API-ключ агента |
| `UWU_API_TIMEOUT_SECONDS` | `30.0` | таймаут запросов к ядру |
| `LLM_BASE_URL` | `https://inference.waw0.amvera.ru/v1` | OpenAI-совместимый base URL |
| `LLM_API_KEY` | — | ключ LLM |
| `LLM_MODEL` | `gpt-4.1` | имя модели |
| `LLM_TEMPERATURE` | `0.3` | температура |
| `LLM_MAX_TOKENS` | `1024` | лимит токенов |
| `CHECKPOINT_DB_URL` | — | PostgreSQL для checkpointer (пусто = in-memory) |
| `CHECKPOINT_SCHEMA` | `agent` | схема checkpointer |

> **LLM-провайдер.** По умолчанию настроен [Amvera LLM Inference](https://docs.amvera.ru/LLM/)
> (OpenAI-совместимый API). Токен копируется в ЛК Amvera в разделе LLM (модель →
> «токен доступа»); модели: `gpt-4.1`, `gpt-5`, `gpt-5.5`, `glm-5.1`, `qwen3_235b`,
> `deepseek-V4`, `llama70b` и др. Любой другой OpenAI-совместимый бэкенд задаётся
> тем же `LLM_BASE_URL`/`LLM_API_KEY`/`LLM_MODEL`.

## Запуск

```bash
cp .env.example .env
# задать UWU_API_KEY и LLM_API_KEY
docker compose up --build
```

Открыть http://localhost:8100/healthz.

## Развёртывание рядом с ядром (общий хостинг)

Модель «1 репозиторий = 1 контейнер»: контейнер `agent` добавляется в ту же
Docker-сеть, что и контейнер ядра UWU, а `UWU_API_BASE_URL` указывает на имя
сервиса ядра (например `http://uwu-app:8000`). Точная топология сети
согласуется при интеграции на хостинг (см. `ROADMAP.md`, точки согласования).

## Проверка готовности

Эндпоинт `/healthz` возвращает `{"status":"ok",...}` (используется HEALTHCHECK в
[`Dockerfile`](../Dockerfile)). Перед деплоем — прогнать тесты (см.
[testing](testing.md)).
