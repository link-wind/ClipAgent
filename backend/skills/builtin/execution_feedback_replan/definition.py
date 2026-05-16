from backend.domain.skills.contracts import SkillDefinition


SKILL_DEFINITION = SkillDefinition(
    id="builtin.execution_feedback_replan",
    version="0.1.0",
    name="Execution Feedback Replan",
    description="Repair-oriented replanning skill for execution feedback.",
    trigger_conditions={"runTypes": ["execution_feedback_replan"]},
    prompts={"repair": "repair.md"},
    handler="backend.skills.builtin.execution_feedback_replan.handlers:build_execution_feedback_replan_request",
)
