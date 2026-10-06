from app.workflow.config import WorkflowSettings


def test_settings_use_qwen_and_mock_mode_by_default():
    settings = WorkflowSettings(_env_file=None)
    assert settings.mock_llm is True
    assert settings.ollama_model == "qwen3:4b"
    assert settings.router_max_attempts == 2


def test_settings_accept_environment_style_values(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("ROUTER_MAX_ATTEMPTS", "3")
    settings = WorkflowSettings(_env_file=None)
    assert settings.mock_llm is False
    assert settings.router_max_attempts == 3

