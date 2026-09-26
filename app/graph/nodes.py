"""Узлы графа LangGraph (фаза 2 — консультация).

Узлы — фабрики, замыкающие :class:`~app.graph.runtime.AgentRuntime` (LLM,
промпты, инструменты). Каждый узел — асинхронная функция от ``AgentState``,
возвращающая частичное обновление состояния. LLM-вызовы имеют детерминированный
fallback (эвристика/заглушка), поэтому граф работает и без сконфигурированного LLM.

Маршрут: ``classify_intent → retrieve_context → generate`` (см. builder).
"""
from __future__ import annotations

import re
from collections.abc import Callable

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

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


def _role(message) -> str:
    return getattr(message, "type", "unknown")


def _format_history(state: AgentState) -> str:
    messages = state.get("messages") or []
    return "\n".join(f"{_role(m)}: {m.content}" for m in messages[-10:])


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
    """Вызывает инструмент, не роняя граф при ошибке/отсутствии инструмента."""
    fn = runtime.tools.get(tool_key)
    if fn is None:
        return None
    try:
        return await fn(**kwargs)
    except Exception:  # noqa: BLE001 — инструмент не должен валить граф
        return None


# --- Узлы ----------------------------------------------------------------------


def make_classify_intent(runtime: AgentRuntime) -> Callable:
    async def classify_intent(state: AgentState) -> dict:
        text = _last_user_text(state)
        prompt = runtime.prompts.get("classify_intent")
        if runtime.llm is None or prompt is None:
            return {"intent": _heuristic_intent(text)}
        rendered = render_prompt(prompt.template, messages=text)
        try:
            resp = await runtime.llm.ainvoke([HumanMessage(content=rendered)])
            raw = str(resp.content or "").strip().lower()
        except Exception:  # noqa: BLE001
            return {"intent": _heuristic_intent(text)}
        for intent in INTENTS:
            if intent in raw:
                return {"intent": intent}
        return {"intent": "fallback"}

    return classify_intent


def make_retrieve_context(runtime: AgentRuntime) -> Callable:
    async def retrieve_context(state: AgentState) -> dict:
        intent = state.get("intent") or "fallback"
        text = _last_user_text(state)
        context: dict = {"intent": intent}

        if intent in ("consultation", "stock", "price", "reorder_suggestion"):
            context["products"] = (
                await _safe_tool(runtime, "search_catalog", query=text) or []
            )
        elif intent == "order_status":
            order_id = _extract_order_id(text)
            context["order"] = (
                await _safe_tool(runtime, "get_order_status", order_id=order_id)
                if order_id
                else None
            )
        elif intent in ("add_to_cart", "create_order"):
            # Запись — только через одобрение оператора (фаза 5).
            context["requires_approval"] = True

        return {"context": context}

    return retrieve_context


def make_generate(runtime: AgentRuntime) -> Callable:
    async def generate(state: AgentState) -> dict:
        intent = state.get("intent") or "fallback"
        context = state.get("context") or {}

        if runtime.llm is None:
            return {"final_answer": _fallback_answer(context)}

        if context.get("requires_approval"):
            return {
                "final_answer": (
                    "Это действие требует подтверждения оператора — "
                    "оформлю запрос, вы получите подтверждение в личном кабинете."
                )
            }

        prompt_key = "reorder_suggestion" if intent == "reorder_suggestion" else "generate"
        prompt = runtime.prompts.get(prompt_key) or runtime.prompts.get("generate")
        if prompt is None:
            return {"final_answer": _FALLBACK_ANSWER}

        system = runtime.prompts.get("system")
        rendered = render_prompt(
            prompt.template,
            history=_format_history(state),
            context=_format_context(context),
            intent=intent,
            reorder=_format_context(context),
        )
        messages: list[BaseMessage] = []
        if system is not None and system.template:
            messages.append(SystemMessage(content=system.template))
        messages.append(HumanMessage(content=rendered))

        try:
            resp = await runtime.llm.ainvoke(messages)
            answer = str(resp.content or "").strip()
        except Exception:  # noqa: BLE001
            return {"final_answer": _FALLBACK_ANSWER}
        return {"final_answer": answer or _FALLBACK_ANSWER}

    return generate
