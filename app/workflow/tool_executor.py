"""Adapter for Member 1's deterministic ``call_tool`` entry point."""

from collections.abc import Callable
from datetime import date
from typing import Any

from app.contracts import ToolResult


ToolCaller = Callable[[Any, str, str | None, dict[str, Any], date], ToolResult]


class CallToolExecutor:
    """Make a module-level dispatcher conform to the workflow dependency."""

    def __init__(self, tools: Any, call_tool: ToolCaller) -> None:
        self._tools = tools
        self._call_tool = call_tool

    def execute(
        self,
        tool_name: str,
        student_id: str | None,
        args: dict[str, Any],
        as_of_date: date,
    ) -> ToolResult:
        return self._call_tool(
            self._tools,
            tool_name,
            student_id,
            args,
            as_of_date,
        )
