from __future__ import annotations

from pathlib import Path

from backend.domain.skills.contracts import PlannerRequest, SkillSelectionRequest


def build_execution_feedback_replan_request(request: SkillSelectionRequest) -> PlannerRequest:
    failed_scene_ids = request.failure_context.get("failedSceneIds", [])
    return PlannerRequest(
        action=request.run_type,
        system_prompt=_read_prompt("repair.md"),
        messages=[{"role": "user", "content": request.user_message}],
        failure_context=request.failure_context,
        retry_strategy_hint="targeted_replan",
        failed_scene_ids=failed_scene_ids,
        output_schema={"type": "agent_plan"},
    )


def _read_prompt(prompt_name: str) -> str:
    prompt_path = Path(__file__).resolve().parent / "prompts" / prompt_name
    return prompt_path.read_text(encoding="utf-8").strip()
