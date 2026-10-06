from types import SimpleNamespace

from app.llm import OllamaLLM
from app.workflow.llm.ollama import _unpack_structured


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_member_four_facade_uses_mock_without_http(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "true")

    def should_not_call(*args, **kwargs):
        raise AssertionError("HTTP must not be called in mock mode")

    monkeypatch.setattr("app.llm.httpx.post", should_not_call)
    result = OllamaLLM.synthesize_explanation(
        question="Am I eligible?",
        retrieved_context="Attendance rule: 80%",
        tool_results="ELIGIBLE",
        answer_type="calculated",
    )

    assert result["model"] == "mock-llm"
    assert result["tokens"] == 0
    assert "ELIGIBLE" in result["text"]
    assert result["fallback_used"] is False


def test_member_four_facade_calls_generate_and_extracts_usage(monkeypatch):
    monkeypatch.setenv("MOCK_LLM", "false")
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama.test:11434")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.1:8b")
    seen = {}

    def fake_post(url, **kwargs):
        seen["url"] = url
        seen.update(kwargs)
        return FakeResponse(
            {
                "response": "You are eligible under the supplied rule.",
                "prompt_eval_count": 40,
                "eval_count": 12,
            }
        )

    monkeypatch.setattr("app.llm.httpx.post", fake_post)
    result = OllamaLLM.synthesize_explanation(
        question="Am I eligible?",
        retrieved_context="Attendance rule: 80%",
        tool_results="ELIGIBLE",
        answer_type="calculated",
    )

    assert seen["url"] == "http://ollama.test:11434/api/generate"
    assert seen["json"]["model"] == "llama3.1:8b"
    assert seen["json"]["stream"] is False
    assert result["tokens"] == 52
    assert result["model"] == "llama3.1:8b"
    assert result["fallback_used"] is False


def test_structured_adapter_extracts_langchain_usage_metadata():
    parsed = {"answer": "ok"}
    raw = SimpleNamespace(
        usage_metadata={"input_tokens": 25, "output_tokens": 5, "total_tokens": 30}
    )

    value, tokens = _unpack_structured(
        {"raw": raw, "parsed": parsed, "parsing_error": None},
        dict,
    )

    assert value == parsed
    assert tokens == 30
