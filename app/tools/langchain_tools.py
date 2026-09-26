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


class AddToCartArgs(BaseModel):
    customer_id: int = Field(description="ID покупателя")
    nomenklatura_id: int = Field(description="ID товара (номенклатуры)")
    quantity: float = Field(description="Количество")


class CreateOrderArgs(BaseModel):
    customer_id: int = Field(description="ID покупателя")
    items: list[dict] = Field(description="Позиции заказа: [{nomenklatura_id, quantity}]")


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


def build_write_tools(
    client: UwuClient, tool_specs: dict[str, ToolSpec]
) -> list[BaseTool]:
    """Write-инструменты (add_to_cart/create_order) — требуют одобрения оператора.

    Эти инструменты регистрируются в LLM (чтобы он мог их предложить), но НЕ
    выполняются напрямую: граф маршрутизирует их вызов в узел ``request_approval``
    (создание ``AgentApproval`` + interrupt). Исполнение происходит после одобрения.
    """
    tools: list[BaseTool] = []

    if "add_to_cart" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.add_to_cart,
                name="add_to_cart",
                description=tool_specs["add_to_cart"].description,
                args_schema=AddToCartArgs,
            )
        )
    if "create_order" in tool_specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=client.create_order,
                name="create_order",
                description=tool_specs["create_order"].description,
                args_schema=CreateOrderArgs,
            )
        )

    return tools
