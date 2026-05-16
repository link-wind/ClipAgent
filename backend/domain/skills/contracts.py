from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SkillDefinition:
    id: str
    version: str
    name: str
    description: str
    trigger_conditions: dict[str, Any] = field(default_factory=dict)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    required_context: list[str] = field(default_factory=list)
    required_tools: list[str] = field(default_factory=list)
    default_role: str = "planner"
    supported_roles: list[str] = field(default_factory=lambda: ["planner"])
    prompts: dict[str, str] = field(default_factory=dict)
    handler: str = ""
    status: str = "active"


@dataclass(frozen=True)
class SkillSelectionRequest:
    session_id: str
    run_id: str
    run_type: str
    user_message: str
    context: dict[str, Any] = field(default_factory=dict)
    failure_context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSelection:
    skill_id: str
    version: str
    reason: str = ""


@dataclass(frozen=True)
class PlannerRequest:
    action: str
    system_prompt: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    context_items: list[dict[str, Any]] = field(default_factory=list)
    output_schema: dict[str, Any] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)
    failure_context: dict[str, Any] = field(default_factory=dict)
    retry_strategy_hint: str = ""
    failed_scene_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class SkillRunSummary:
    skill_id: str
    skill_version: str
    status: str
    input_summary: str = ""
    output_summary: str = ""
    error_message: str = ""
