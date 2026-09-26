# Тестирование

## Подход

TDD, как в ядре UWU. Тесты — часть системы и проверка готовности перед деплоем.
Юнит-тесты не требуют PostgreSQL: граф работает на in-memory checkpointer'е,
REST проверяется через ASGI-транспорт httpx.

## Запуск

```bash
pytest tests/ -v          # все тесты
ruff check app tests      # линтер
mypy app                  # type-check
```

## Структура

| Файл | Покрытие |
| --- | --- |
| `tests/test_healthz.py` | control-plane: healthz, корневой, webhook |
| `tests/test_config.py` | настройки (дефолты, override через env) |
| `tests/test_graph.py` | граф: запуск заглушки, сохранение истории |
| `tests/test_client.py` | клиент ядра: авторизация, контракт путей/методов |
| `tests/test_factory.py` | фабрика LLM: нет ключа → `None`, ключ → модель |

## Фикстуры (`tests/conftest.py`)

- `client` — ASGI-клиент (httpx) для тестов control-plane.

## Слои тестирования (по мере реализации фаз)

| Слой | Что покрываем | Инструмент |
| --- | --- | --- |
| Юнит (граф) | каждый узел на фиксированных состояниях | pytest, мок LLM |
| Промпты | рендер (переменные, версия), регрессия | pytest + eval-набор |
| Инструменты | валидация `params_schema`, права | pytest + контракт-тесты |
| Интеграция | против реального API ядра (`uwu_test`) | pytest-asyncio |
| HITL | interrupt/resume одобрения | pytest + мок checkpointer |
| Eval | качество ответов на золотом датасете | LangSmith/Langfuse |
| Безопасность | промпт-инъекции, права, rate limit | pytest (adversarial) |

Требования: мок LLM в юнит-тестах; контракт-тесты привязаны к версии API ядра;
золотой датасет версионируется в репозитории; CI — pytest + ruff + mypy.
