"""Оркестратор агента: сборка рантайма и обработка сообщений.

Связывает слои: загружает конфигурацию (промпты/инструменты) из ядра UWU,
строит LLM и инструменты, компилирует граф и выполняет его для входящих
сообщений. Обрабатывает HITL-прерывания (одобрение write-действий) и пишет
аудит запусков.

См. также: :mod:`app.config_loader.loader`, :mod:`app.llm.factory`,
:mod:`app.tools.langchain_tools`, :mod:`app.graph.builder`.
"""
from __future__ import annotations

import time
from uuid import uuid4

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from app.clients.uwu import UwuClient
from app.config_loader.loader import load_agent_config
from app.core.config import Settings
from app.core.logging import get_logger
from app.graph.runtime import AgentRuntime
from app.llm.factory import build_chat_model
from app.tools.langchain_tools import build_langchain_tools, build_write_tools
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
    write_tools = build_write_tools(client, config.tools)
    write_tool_names = frozenset(
        key
        for key, spec in config.tools.items()
        if spec.approval_policy in ("threshold", "always")
    )
    runtime = AgentRuntime(
        llm=llm,
        prompts=config.prompts,
        tools=tools,
        lc_tools=lc_tools + write_tools,
        write_tool_names=write_tool_names,
        client=client,
        settings=settings,
    )
    return runtime, client


def _thread_config(chat_id: int) -> RunnableConfig:
    return {"configurable": {"thread_id": f"chat-{chat_id}"}}


def _get_interrupt(graph: CompiledStateGraph, config: RunnableConfig):
    """Возвращает значение прерывания графа (или None, если граф завершён)."""
    try:
        snapshot = graph.get_state(config)
    except Exception:  # noqa: BLE001
        return None
    if snapshot.tasks:
        task = snapshot.tasks[0]
        if task.interrupts:
            return task.interrupts[0].value
    return None


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
    """Обрабатывает входящее сообщение графом.

    ``thread_id`` привязан к чату — checkpointer сохраняет историю. Если граф
    прервался на одобрении (HITL), возвращает ``{"status": "approval_pending",
    "interrupt": {...}}``; иначе — состояние с ``final_answer``. При наличии
    ``client`` пишет результат в журнал ядра (``POST /api/agent/runs``).
    """
    trace_id = uuid4().hex
    started = time.monotonic()
    config = _thread_config(chat_id)
    try:
        result = await graph.ainvoke(
            {
                "messages": [HumanMessage(content=text)],
                "chat_id": chat_id,
                "channel": channel,
                "customer_id": customer_id,
                "trace_id": trace_id,
            },
            config=config,
        )
        status = "ok"
        error = None
    except Exception as exc:
        logger.exception("Ошибка обработки сообщения чата %s", chat_id)
        result = {"intent": None, "context": {}, "final_answer": _FALLBACK_ANSWER}
        status = "error"
        error = str(exc)

    interrupt_value = _get_interrupt(graph, config)
    if interrupt_value is not None:
        status = "approval_pending"

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

    if interrupt_value is not None:
        return {
            "status": "approval_pending",
            "interrupt": interrupt_value,
            "intent": result.get("intent"),
        }
    return result


async def resume_graph(
    graph: CompiledStateGraph,
    *,
    chat_id: int,
    approved: bool,
) -> dict:
    """Возобновляет прерванный граф после решения оператора по одобрению."""
    result = await graph.ainvoke(
        Command(resume={"approved": approved}),
        config=_thread_config(chat_id),
    )
    return result
