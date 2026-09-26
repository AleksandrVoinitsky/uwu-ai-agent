"""Eval-тесты: золотой датасет классификации намерений.

Датасет версионируется в репозитории (``data/golden_dataset.json``) и гоняется
как регрессия на детерминированной классификации (эвристика без LLM).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.messages import HumanMessage

from app.graph.builder import build_graph
from tests.conftest import make_runtime

_DATASET_PATH = Path(__file__).parent.parent / "data" / "golden_dataset.json"
_DATASET = json.loads(_DATASET_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", _DATASET, ids=[c["message"] for c in _DATASET])
async def test_intent_classification(case):
    graph = build_graph(make_runtime())
    result = await graph.ainvoke(
        {"messages": [HumanMessage(content=case["message"])], "chat_id": 1},
        config={"configurable": {"thread_id": "eval"}},
    )
    assert result["intent"] == case["intent"]
