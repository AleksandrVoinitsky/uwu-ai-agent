"""Узлы графа LangGraph (консультация + сбор заказов без одобрения).

Узлы — фабрики, замыкающие :class:`~app.graph.runtime.AgentRuntime`. Маршрут:

```
START → classify_intent → decide_action ⇄ call_tool → finalize → END
```

``decide_action`` — LLM с привязанными инструментами: либо отвечает, либо
возвращает tool_calls; ``call_tool`` исполняет их (с подстановкой ``customer_id``
из состояния чата для инструментов покупателя) и возвращает результат в
``decide_action``. Без LLM ``decide_action`` деградирует к детерминированному
ответу (поиск по каталогу/список товаров).

Одобрение оператора (HITL) убрано: агент собирает заказы и корзину сам, но
документ создаётся в статусе ``DRAFT`` (проведение — за оператором).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage

from app.graph.runtime import AgentRuntime, render_prompt
from app.graph.state import AgentState
from app.tools.uwu_tools import CUSTOMER_SCOPED_TOOLS

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

_NO_CUSTOMER = (
    "Чтобы собрать корзину или оформить заказ, мне нужен ваш профиль покупателя. "
    "Уточните, пожалуйста, номер телефона или зайдите в личный кабинет магазина."
)


# --- Вспомогательные -----------------------------------------------------------


def _last_user_text(state: AgentState) -> str:
    messages = state.get("messages") or []
    if not messages:
        return ""
    return str(getattr(messages[-1], "content", "") or "")


def _heuristic_intent(text: str) -> str:
    """Детерминированная классификация по ключевым словам (fallback без LLM).

    Порядок важен: «оформить/заказать» (создание) проверяется раньше «статуса
    заказа», т.к. слово «заказ» встречается в обоих случаях.
    """
    t = text.lower()
    if any(k in t for k in ("оформи", "закажи", "закажите", "купи", "купить", "create order")):
        return "create_order"
    if any(k in t for k in ("статус", "status", "отследить", "где мой заказ")):
        return "order_status"
    if any(k in t for k in ("наличие", "остат", "в наличии", "на складе", "stock")):
        return "stock"
    if any(k in t for k in ("цена", "стоит", "сколько стоит", "почём", "price")):
        return "price"
    if any(k in t for k in ("добавь", "в корзин", "add", "cart")):
        return "add_to_cart"
    if any(k in t for k in ("повтори", "докупи", "список покупок", "reorder")):
        return "reorder_suggestion"
    return "consultation"


def _extract_order_id(text: str) -> int | None:
    m = re.search(r"\b(\d{1,9})\b", text)
    return int(m.group(1)) if m else None


def _fallback_answer(context: dict) -> str:
    """Детерминированный ответ без LLM (перечисляет найденные товары)."""
    products = context.get("products")
    if products:
        lines = [
            f"• {p.get('name')} — {p.get('price') or '?'} ₽, остаток {p.get('stock') or '?'}"
            for p in products[:5]
        ]
        return "Нашёл для вас:\n" + "\n".join(lines)
    if context.get("need_clarify"):
        return "Уточните, пожалуйста, какие товары и в каком количестве добавить в заказ."
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
        context["need_clarify"] = True
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
        # Чёткие намерения («добавь … в корзину», «оформи заказ», «остатки»,
        # «цена») классифицируем детерминированно — это надёжнее, чем LLM, и не
        # тратит токены. LLM используется только для неоднозначных сообщений.
        heuristic = _heuristic_intent(text)
        if heuristic != "consultation":
            return {"intent": heuristic}

        prompt = runtime.prompts.get("classify_intent")
        if runtime.llm is None or prompt is None:
            return {"intent": heuristic}
        rendered = render_prompt(prompt.template, messages=text)
        try:
            resp = await runtime.llm.ainvoke([BaseMessage(content=rendered, type="human")])
            raw = str(getattr(resp, "content", "") or "").strip().lower()
        except Exception:  # noqa: BLE001
            return {"intent": heuristic}
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


def make_call_tool(runtime: AgentRuntime) -> Callable:
    """Исполняет вызовы инструментов из последнего сообщения LLM.

    Для инструментов, привязанных к покупателю (``get_cart``/``add_to_cart``/
    ``create_order``), подставляет ``customer_id`` из состояния чата — модель не
    должна его придумывать. Результат возвращается как ``ToolMessage``, чтобы
    ``decide_action`` сгенерировал финальный ответ.
    """

    async def call_tool(state: AgentState) -> dict:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        tool_calls = getattr(last, "tool_calls", None) or []
        customer_id = state.get("customer_id")

        results: list[ToolMessage] = []
        for tc in tool_calls:
            name = tc.get("name")
            call_id = tc.get("id")
            args = dict(tc.get("args") or {})
            fn = runtime.tools.get(name)
            if fn is None:
                results.append(ToolMessage(content="инструмент не найден", tool_call_id=call_id, name=name))
                continue
            if name in CUSTOMER_SCOPED_TOOLS:
                if customer_id is None:
                    results.append(ToolMessage(content=_NO_CUSTOMER, tool_call_id=call_id, name=name))
                    continue
                args["customer_id"] = customer_id
            try:
                out = await fn(**args)
                content = json.dumps(out, ensure_ascii=False, default=str)
            except Exception as exc:  # noqa: BLE001 — ошибка инструмента не валит граф
                content = f"ошибка: {exc}"
            results.append(ToolMessage(content=content, tool_call_id=call_id, name=name))

        return {"messages": results}

    return call_tool


def make_finalize(runtime: AgentRuntime) -> Callable:
    def finalize(state: AgentState) -> dict:
        messages = state.get("messages") or []
        last = messages[-1] if messages else None
        content = str(getattr(last, "content", "") or "").strip()
        return {"final_answer": content or _FALLBACK_ANSWER}

    return finalize
