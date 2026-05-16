from __future__ import annotations

from pathlib import Path

from backend.domain.skills.contracts import PlannerRequest, SkillSelectionRequest


PROMPT_FILE_BY_RUN_TYPE = {
    "initial_planning": "planner.md",
    "user_revision": "revision.md",
    "grounding_replan": "grounding_replan.md",
}


def build_product_intro_planner_request(request: SkillSelectionRequest) -> PlannerRequest:
    prompt_name = PROMPT_FILE_BY_RUN_TYPE.get(request.run_type, "planner.md")
    context_items = [{"type": key, "value": value} for key, value in request.context.items()]
    return PlannerRequest(
        action=request.run_type,
        system_prompt=_read_prompt(prompt_name),
        messages=[{"role": "user", "content": request.user_message}],
        context_items=context_items,
        output_schema={"type": "agent_plan"},
        retry_strategy_hint="none",
    )


def _read_prompt(prompt_name: str) -> str:
    prompt_path = Path(__file__).resolve().parent / "prompts" / prompt_name
    return prompt_path.read_text(encoding="utf-8").strip()
