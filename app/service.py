"""Оркестратор агента: сборка рантайма и обработка сообщений.

Связывает слои: загружает конфигурацию (промпты/инструменты) из ядра UWU,
строит LLM и инструменты, компилирует граф и выполняет его для входящих
сообщений.

См. также: :mod:`app.config_loader.loader`, :mod:`app.llm.factory`,
:mod:`app.tools.uwu_tools`, :mod:`app.graph.builder`.
"""
from __future__ import annotations

from langchain_core.messages import HumanMessage
from langgraph.graph.state import CompiledStateGraph

from app.clients.uwu import UwuClient
from app.config_loader.loader import load_agent_config
from app.core.config import Settings
from app.graph.runtime import AgentRuntime
from app.llm.factory import build_chat_model
from app.tools.langchain_tools import build_langchain_tools
from app.tools.uwu_tools import build_tools


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
) -> dict:
    """Обрабатывает входящее сообщение графом и возвращает состояние.

    ``thread_id`` привязан к чату — checkpointer сохраняет историю диалога между
    сообщениями одного чата.
    """
    result = await graph.ainvoke(
        {
            "messages": [HumanMessage(content=text)],
            "chat_id": chat_id,
            "channel": channel,
            "customer_id": customer_id,
        },
        config={"configurable": {"thread_id": f"chat-{chat_id}"}},
    )
    return result
