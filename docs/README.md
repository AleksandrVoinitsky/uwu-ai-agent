# uwu-ai-agent — документация

uwu-ai-agent — AI-агент (консультант покупателей и чат-ассистент) для проекта
UWU. Отдельный сервис и контейнер, клиент REST API ядра UWU.

## Содержание

| Раздел | Описание |
| --- | --- |
| [architecture](architecture.md) | Архитектура, стек, карта модулей |
| [graph](graph.md) | Граф LangGraph: состояние, узлы, рёбра |
| [integration](integration.md) | Интеграция с ядром UWU: эндпоинты, API-ключ, поток, HITL |
| [CORE_CONTRACT](CORE_CONTRACT.md) | Контракт для разработчика ядра UWU (что реализовать) |
| [testing](testing.md) | Автотесты (TDD), слои, запуск |
| [deployment](deployment.md) | Сборка Docker, развёртывание, переменные окружения |

## Ключевые принципы

- **Агент — клиент API ядра**, не пишет в БД ядра и не дублирует бизнес-логику.
- **Слоистая архитектура** (api → graph/clients → core), SOLID, TDD.
- **Промпты/инструменты управляются из админки ядра**, агент загружает через API.
- **Human-in-the-loop по порогу**: чтение — авто; мутирующие ниже порога — авто;
  выше — одобрение оператора.

Полная спецификация агента — в ядре UWU: [`docs/ai-agent.md`](https://github.com/AleksandrVoinitsky/UWU/blob/main/docs/ai-agent.md).
