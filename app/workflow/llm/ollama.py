"""Ollama-backed structured router with validation and safe fallback."""

from datetime import date
from typing import Any

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama

from app.contracts import RouteDecision
from app.workflow.config import WorkflowSettings
from app.workflow.llm.base import RouteOutcome
from app.workflow.llm.mock import MockWorkflowLLM
from app.workflow.routing_policy import normalize_route_decision


ROUTER_SYSTEM_PROMPT = """You route university student-service questions.

Return a value matching the supplied JSON schema. Do not answer the question.

Allowed categories:
- policy_fact
- procedure
- personal_data
- eligibility
- multi_step
- not_answerable

Allowed tools:
- get_attendance
- get_results
- check_exam_eligibility
- check_supplementary_eligibility
- check_placement_eligibility
- run_what_if

Rules:
1. Policy facts and procedures need retrieval.
2. Personal data needs a student tool.
3. Eligibility needs retrieval for the rule and a deterministic tool for the result.
4. Multi-step and what-if requests may need both retrieval and tools.
5. Extract course_code, programme, batch, exam_type, and other useful entities.
6. Never extract or invent student_id. Identity comes only from trusted request context.
7. get_attendance and get_results accept an optional course_code or course_name.
8. Exam and supplementary eligibility require a course_code or course_name.
9. For run_what_if, put a changes object in entities. Allowed changes are
   active_backlogs, pass_courses, cgpa, and classes_attended.
10. Never request a tool outside the allowed list.
"""


class OllamaWorkflowLLM:
    """Structured Qwen router that retries failures and then falls back safely."""

    def __init__(
        self,
        settings: WorkflowSettings,
        structured_router: Any | None = None,
    ) -> None:
        self.settings = settings
        self.model_name = settings.ollama_model
        self._fallback = MockWorkflowLLM()

        if structured_router is not None:
            self._structured_router = structured_router
            return

        chat = ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0,
            reasoning=False,
            keep_alive=settings.ollama_keep_alive,
            num_ctx=settings.ollama_num_ctx,
            num_predict=settings.ollama_num_predict,
            validate_model_on_init=False,
            async_client_kwargs={"timeout": settings.llm_timeout_seconds},
        )
        self._structured_router = chat.with_structured_output(
            RouteDecision,
            method="json_schema",
        )

    async def health_check(self) -> tuple[bool, str]:
        """Confirm that Ollama is reachable and the configured model exists."""

        url = f"{self.settings.ollama_base_url.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.get(url)
                response.raise_for_status()
                models = {
                    model.get("name")
                    for model in response.json().get("models", [])
                    if model.get("name")
                }
        except (httpx.HTTPError, ValueError) as exc:
            return False, f"Ollama health check failed: {exc}"

        if self.settings.ollama_model not in models:
            return False, f"Model {self.settings.ollama_model!r} is not installed."
        return True, "ok"

    async def route(self, question: str, as_of_date: date) -> RouteOutcome:
        errors: list[str] = []
        messages = [
            SystemMessage(content=ROUTER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"as_of_date: {as_of_date.isoformat()}\n"
                    f"question: {question}"
                )
            ),
        ]

        for attempt in range(1, self.settings.router_max_attempts + 1):
            try:
                decision = await self._structured_router.ainvoke(messages)
                if not isinstance(decision, RouteDecision):
                    decision = RouteDecision.model_validate(decision)
                decision = normalize_route_decision(question, decision)
                return RouteOutcome(
                    decision=decision,
                    attempts=attempt,
                    fallback_used=False,
                    errors=errors,
                    model_name=self.model_name,
                )
            except Exception as exc:  # provider and schema failures share one fallback path
                errors.append(f"router attempt {attempt} failed: {type(exc).__name__}: {exc}")

        fallback = await self._fallback.route(question, as_of_date)
        return RouteOutcome(
            decision=fallback.decision,
            attempts=self.settings.router_max_attempts,
            fallback_used=True,
            errors=errors,
            model_name=self.model_name,
        )

