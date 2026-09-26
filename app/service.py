"""Оркестратор агента: сборка рантайма и обработка сообщений.

Связывает слои: загружает конфигурацию (промпты/инструменты) из ядра UWU,
строит LLM и инструменты, компилирует граф и выполняет его для входящих
сообщений.

См. также: :mod:`app.config_loader.loader`, :mod:`app.llm.factory`,
:mod:`app.tools.uwu_tools`, :mod:`app.graph.builder`.
"""
from __future__ import annotations

import time
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.clients.uwu import UwuClient
from app.config_loader.loader import load_agent_config
from app.core.config import Settings
from app.core.logging import get_logger
from app.graph.runtime import AgentRuntime
from app.llm.factory import build_chat_model
from app.tools.langchain_tools import build_langchain_tools
from app.tools.uwu_tools import build_tools

logger = get_logger("app.service")

_FALLBACK_ANSWER = "Извините, я сейчас не могу ответить. Оператор свяжется с вами."


async def build_runtime(settings: Settings) -> tuple[AgentRuntime, UwuClient]:
    """Собирает рантайм агента и открытый HTTP-клиент ядра.

    Возвращает ``(runtime, client)`` — клиент нужно закрыть по окончании работы.
    """
    client = UwuClient(
        settings.uwu_api_base_url,
        api_key=settings.uwu_api_key,
        timeout=settings.uwu_api_timeout_seconds,
    )
    config = await load_agent_config(client, settings)
    llm = build_chat_model(settings)
    tools = build_tools(client)
    lc_tools = build_langchain_tools(client, config.tools)
    runtime = AgentRuntime(
        llm=llm,
        prompts=config.prompts,
        tools=tools,
        lc_tools=lc_tools,
        settings=settings,
    )
    return runtime, client


async def process_message(
    runtime: AgentRuntime,
    graph: CompiledStateGraph,
    *,
    chat_id: int,
    text: str,
    channel: str = "site",
    customer_id: int | None = None,
    client: UwuClient | None = None,
) -> dict:
    """Обрабатывает входящее сообщение графом и возвращает состояние.

    ``thread_id`` привязан к чату — checkpointer сохраняет историю диалога между
    сообщениями одного чата. При наличии ``client`` пишет результат запуска в
    журнал ядра (``POST /api/agent/runs``, fire-and-forget — не роняет обработку).
    """
    trace_id = uuid4().hex
    started = time.monotonic()
    try:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=text)],
                "chat_id": chat_id,
                "channel": channel,
                "customer_id": customer_id,
                "trace_id": trace_id,
            },
            config={"configurable": {"thread_id": f"chat-{chat_id}"}},
        )
        status = "ok"
        error = None
    except Exception as exc:
        logger.exception("Ошибка обработки сообщения чата %s", chat_id)
        result = {"intent": None, "context": {}, "final_answer": _FALLBACK_ANSWER}
        status = "error"
        error = str(exc)

    if client is not None:
        try:
            await client.post_run(
                trace_id=trace_id,
                chat_id=chat_id,
                customer_id=customer_id,
                intent=result.get("intent"),
                model=runtime.settings.llm_model,
                status=status,
                error=error,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        except Exception:
            logger.warning("Не удалось записать запуск агента в ядро", exc_info=True)

    return result
