import os
import time
import requests
import json
from typing import Dict, Any, Optional

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
MOCK_LLM_MODE = os.getenv("MOCK_LLM", "false").lower() in ("true", "1", "yes")

class OllamaLLM:
    """
    Ollama Local LLM Integration Module.
    Connects to Ollama REST API (/api/generate) running locally or inside Docker host.
    Supports automatic MOCK_LLM fallback mode when Ollama is offline.
    """

    @classmethod
    def generate(
        cls,
        prompt: str,
        system_prompt: str = "You are an accurate, grounded University Student Services Assistant. Base answers strictly on provided context. Never fabricate information.",
        model: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Sends generation request to Ollama HTTP server.
        Returns:
            {
                "text": str,
                "model": str,
                "tokens": int,
                "latency_ms": int,
                "status": "success" | "mock_fallback" | "error"
            }
        """
        target_model = model or DEFAULT_MODEL
        t0 = time.time()

        # If MOCK_LLM environment variable is enabled, use mock response
        if MOCK_LLM_MODE:
            return {
                "text": f"[MOCK_LLM Response]: Synthesized answer based on prompt context.",
                "model": f"mock-{target_model}",
                "tokens": len(prompt.split()) + 30,
                "latency_ms": 15,
                "status": "mock_fallback"
            }

        url = f"{OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=12)
            latency_ms = int((time.time() - t0) * 1000)

            if response.status_code == 200:
                data = response.json()
                eval_tokens = data.get("eval_count", 0) + data.get("prompt_eval_count", 0)
                return {
                    "text": data.get("response", "").strip(),
                    "model": target_model,
                    "tokens": eval_tokens or (len(prompt.split()) * 2),
                    "latency_ms": max(1, latency_ms),
                    "status": "success"
                }
            else:
                # API error -> Fallback
                return cls._mock_fallback(prompt, target_model, latency_ms, f"Ollama HTTP {response.status_code}")

        except Exception as e:
            latency_ms = int((time.time() - t0) * 1000)
            return cls._mock_fallback(prompt, target_model, latency_ms, str(e))

    @classmethod
    def _mock_fallback(cls, prompt: str, model: str, latency_ms: int, error_msg: str) -> Dict[str, Any]:
        """Graceful fallback when Ollama service is unreachable."""
        return {
            "text": "[OLLAMA_FALLBACK]: Service offline or model loading. Returning deterministic system response.",
            "model": f"{model} (offline fallback)",
            "tokens": len(prompt.split()) + 20,
            "latency_ms": max(1, latency_ms),
            "status": f"fallback: {error_msg}"
        }

    @classmethod
    def synthesize_explanation(
        cls,
        question: str,
        retrieved_context: str,
        tool_results: str,
        answer_type: str
    ) -> Dict[str, Any]:
        """
        Synthesizes student-facing plain language explanation using Ollama LLM.
        """
        system_prompt = (
            "You are the official University Student Services AI Assistant. "
            "Explain eligibility decisions and policy facts clearly to students. "
            "Do NOT perform math yourself; use the provided tool calculation results. "
            "Do NOT fabricate information outside the provided retrieved context."
        )

        user_prompt = f"""
        Student Question: {question}
        Answer Classification: {answer_type}
        
        [Retrieved Policy Context]:
        {retrieved_context if retrieved_context else "None"}
        
        [Deterministic Tool Results]:
        {tool_results if tool_results else "None"}
        
        Provide a concise, friendly 2-3 sentence explanation for the student.
        """

        return cls.generate(prompt=user_prompt, system_prompt=system_prompt)
