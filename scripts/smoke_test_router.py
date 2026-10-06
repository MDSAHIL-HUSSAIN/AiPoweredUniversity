"""Run one real structured-routing request against the configured Ollama model."""

import asyncio
from datetime import date

from app.workflow.config import WorkflowSettings
from app.workflow.llm import OllamaWorkflowLLM


async def main() -> None:
    settings = WorkflowSettings(mock_llm=False)
    llm = OllamaWorkflowLLM(settings)
    healthy, detail = await llm.health_check()
    if not healthy:
        raise SystemExit(detail)

    outcome = await llm.route(
        "Am I eligible for the supplementary exam in CS201?",
        date.today(),
    )
    print(outcome.model_dump_json(indent=2))


if __name__ == "__main__":
    asyncio.run(main())

