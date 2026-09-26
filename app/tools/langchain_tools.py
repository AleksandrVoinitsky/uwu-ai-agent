"""LangChain-инструменты агента (для tool-calling в LLM).

Оборачивают tool-friendly эндпоинты ядра в ``StructuredTool`` с типизированной
схемой аргументов, чтобы LLM мог выбирать инструмент и передавать аргументы.
Имена/описания берутся из реестра инструментов ядра (``agent_tools``).

См. также: :mod:`app.tools.uwu_tools`, docs/CORE_CONTRACT.md.
"""
from __future__ import annotations

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field

from app.clients.uwu import UwuClient
from app.config_loader.loader import ToolSpec


class SearchCatalogArgs(BaseModel):
    query: str = Field(description="Поисковый запрос: название или артикул товара")


class GetStockArgs(BaseModel):
    nomenklatura_id: int = Field(description="ID товара (номенклатуры)")


class GetCartArgs(BaseModel):
    customer_id: int = Field(description="ID покупателя")


class GetZakazArgs(BaseModel):
    order_id: int = Field(description="ID заявки/заказа покупателя")


def build_langchain_tools(
    client: UwuClient, tool_specs: dict[str, ToolSpec]
) -> list[BaseTool]:
    """Собирает LangChain-инструменты чтения из реестра инструментов ядра.

    Инструмент создаётся только если он включён в реестре (ключ присутствует в
    ``tool_specs``). Ключи совпадают с ``agent_tools.key`` ядра.
    """
    tools: list[BaseTool] = []

    if "search_catalog" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.search_catalog,
                name="search_catalog",
                description=tool_specs["search_catalog"].description,
                args_schema=SearchCatalogArgs,
            )
        )
    if "get_stock" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.get_stock,
                name="get_stock",
                description=tool_specs["get_stock"].description,
                args_schema=GetStockArgs,
            )
        )
    if "get_cart" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.get_cart,
                name="get_cart",
                description=tool_specs["get_cart"].description,
                args_schema=GetCartArgs,
            )
        )
    if "get_order_status" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.get_zakaz,
                name="get_order_status",
                description=tool_specs["get_order_status"].description,
                args_schema=GetZakazArgs,
            )
        )

    return tools
