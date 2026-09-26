"""Узлы графа LangGraph (фаза 3 — tool-calling).

Узлы — фабрики, замыкающие :class:`~app.graph.runtime.AgentRuntime`. Маршрут:

```
START → classify_intent → decide_action ⇄ call_tool → finalize → END
```

``decide_action`` — LLM с привязанными read-инструментами: либо отвечает, либо
возвращает tool_calls; ``call_tool`` (``ToolNode``) исполняет их, результат
возвращается в ``decide_action``. Без LLM ``decide_action`` деградирует к
детерминированному ответу (поиск по каталогу/список товаров).
"""
from __future__ import annotations

import re
from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage

from app.graph.runtime import AgentRuntime, render_prompt
from app.graph.state import AgentState

INTENTS = (
    "consultation",
    "stock",
    "price",
    "order_status",
    "add_to_cart",
    "create_order",
    "reorder_suggestion",
    "fallback",
)

_FALLBACK_ANSWER = "Извините, я сейчас не могу ответить. Оператор свяжется с вами."


# --- Вспомогательные -----------------------------------------------------------


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    return str(getattr(messages[-1], "content", "") or "")


def _heuristic_intent(text: str) -> str:
    """Детерминированная классификация по ключевым словам (fallback без LLM)."""
    t = text.lower()
    if any(k in t for k in ("статус", "заказ", "order", "status")):
        return "order_status"
    if any(k in t for k in ("наличие", "остат", "в наличии", "на складе", "stock")):
        return "stock"
    if any(k in t for k in ("цена", "стоит", "сколько стоит", "почём", "price")):
        return "price"
    if any(k in t for k in ("добавь", "в корзин", "add", "cart")):
        return "add_to_cart"
    if any(k in t for k in ("повтори", "докупи", "список покупок", "reorder")):
        return "reorder_suggestion"
    if any(k in t for k in ("оформи", "купи", "закажи", "create order")):
        return "create_order"
    return "consultation"


def _extract_order_id(text: str) -> int | None:
    m = re.search(r"\b(\d{1,9})\b", text)
    return int(m.group(1)) if m else None


def _format_context(context: dict) -> str:
    parts: list[str] = []
    products = context.get("products")
    if products:
        parts.append(
            "Товары: "
            + "; ".join(
                f"{p.get('name')} (цена {p.get('price')}, остаток {p.get('stock')})"
                for p in products[:10]
            )
        )
    order = context.get("order")
    if order:
        parts.append(f"Заказ: {order}")
    if context.get("requires_approval"):
        parts.append("Требуется одобрение оператора.")
    return "\n".join(parts) if parts else "(нет данных)"


def _fallback_answer(context: dict) -> str:
    """Детерминированный ответ без LLM (перечисляет найденные товары)."""
    products = context.get("products")
    if products:
        lines = [
            f"• {p.get('name')} — {p.get('price') or '?'} ₽, остаток {p.get('stock') or '?'}"
            for p in products[:5]
        ]
        return "Нашёл для вас:\n" + "\n".join(lines)
    if context.get("requires_approval"):
        return "Это действие требует подтверждения оператора."
    return _FALLBACK_ANSWER


async def _safe_tool(runtime: AgentRuntime, tool_key: str, **kwargs):
    fn = runtime.tools.get(tool_key)
    if fn is None:
        return None
    try:
        return await fn(**kwargs)
    except Exception:  # noqa: BLE001 — инструмент не должен валить граф
        return None


async def _deterministic_context(runtime: AgentRuntime, state: AgentState, intent: str) -> dict:
    """Детерминированное извлечение контекста (без LLM)."""
    text = _last_user_text(state)
    context: dict = {"intent": intent}
    if intent in ("consultation", "stock", "price", "reorder_suggestion"):
        context["products"] = await _safe_tool(runtime, "search_catalog", query=text) or []
    elif intent == "order_status":
        order_id = _extract_order_id(text)
        context["order"] = (
            await _safe_tool(runtime, "get_order_status", order_id=order_id)
            if order_id
            else None
        )
    elif intent in ("add_to_cart", "create_order"):
        context["requires_approval"] = True
    return context


def _system_prompt(runtime: AgentRuntime, intent: str) -> str:
    """Собирает системную инструкцию: роль + правила + инструкция генерации."""
    system = runtime.prompts.get("system")
    generate = runtime.prompts.get("generate")
    parts: list[str] = []
    if system is not None and system.template:
        parts.append(system.template)
    if generate is not None and generate.template:
        parts.append(
            render_prompt(
                generate.template,
                intent=intent,
                history="",
                context="(собери нужные данные через доступные инструменты)",
                reorder="",
            )
        )
    return "\n\n".join(parts)


# --- Узлы ----------------------------------------------------------------------


def make_classify_intent(runtime: AgentRuntime) -> Callable:
    async def classify_intent(state: AgentState) -> dict:
        text = _last_user_text(state)
        prompt = runtime.prompts.get("classify_intent")
        if runtime.llm is None or prompt is None:
            return {"intent": _heuristic_intent(text)}
        rendered = render_prompt(prompt.template, messages=text)
        try:
            resp = await runtime.llm.ainvoke([BaseMessage(content=rendered, type="human")])
            raw = str(getattr(resp, "content", "") or "").strip().lower()
        except Exception:  # noqa: BLE001
            return {"intent": _heuristic_intent(text)}
        for intent in INTENTS:
            if intent in raw:
                return {"intent": intent}
        return {"intent": "fallback"}

    return classify_intent


def make_decide_action(runtime: AgentRuntime) -> Callable:
    async def decide_action(state: AgentState) -> dict:
        intent = state.get("intent") or "fallback"

        # Без LLM — детерминированный ответ (без tool-calling).
        if runtime.llm is None:
            context = await _deterministic_context(runtime, state, intent)
            return {"context": context, "messages": [AIMessage(content=_fallback_answer(context))]}

        model = runtime.llm
        messages: list[BaseMessage] = [SystemMessage(content=_system_prompt(runtime, intent))]
        messages.extend(state.get("messages") or [])

        try:
            if runtime.lc_tools:
                resp = await model.bind_tools(runtime.lc_tools).ainvoke(messages)
            else:
                resp = await model.ainvoke(messages)
        except Exception:  # noqa: BLE001 — degrade gracefully
            context = await _deterministic_context(runtime, state, intent)
            return {"context": context, "messages": [AIMessage(content=_fallback_answer(context))]}

        return {"messages": [resp]}

    return decide_action


def make_finalize(runtime: AgentRuntime) -> Callable:
    def finalize(state: AgentState) -> dict:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        content = str(getattr(last, "content", "") or "").strip()
        return {"final_answer": content or _FALLBACK_ANSWER}

    return finalize
