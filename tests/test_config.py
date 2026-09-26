"""Тесты конфигурации (pydantic-settings)."""
from __future__ import annotations

from app.core.config import Settings


def test_defaults():
    s = Settings(_env_file=None)
    assert s.environment == "production"
    assert s.agent_port == 8100
    assert s.llm_model == "gpt-4.1"
    assert s.llm_temperature == 0.3
    assert s.checkpoint_db_url is None
    assert s.checkpoint_schema == "agent"
    assert s.is_production is True


def test_env_override(monkeypatch):
    monkeypatch.setenv("UWU_API_BASE_URL", "http://core:9000")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")
    monkeypatch.setenv("ENVIRONMENT", "development")
    s = Settings(_env_file=None)
    assert s.uwu_api_base_url == "http://core:9000"
    assert s.llm_api_key == "sk-test"
    assert s.is_production is False
