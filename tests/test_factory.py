"""Тесты фабрики LLM-моделей."""
from __future__ import annotations

from app.core.config import Settings
from app.llm.factory import build_chat_model


def test_no_model_without_key():
    s = Settings(_env_file=None, llm_api_key="")
    assert build_chat_model(s) is None


def test_model_built_with_key():
    s = Settings(
        _env_file=None,
        llm_api_key="sk-test",
        llm_model="test-model",
        llm_base_url="http://llm.local/v1",
    )
    model = build_chat_model(s)
    assert model is not None
    assert model.model_name == "test-model"
    assert model.openai_api_base == "http://llm.local/v1"
