"""Contracts for deterministic student-data and rule tools."""

from typing import Any

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    tool_name: str
    success: bool
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    applied_rule_ids: list[str] = Field(default_factory=list)
    error: str | None = None


class ToolInvocation(BaseModel):
    tool: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)

