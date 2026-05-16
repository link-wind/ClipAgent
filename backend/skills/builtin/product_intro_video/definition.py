from backend.domain.skills.contracts import SkillDefinition


SKILL_DEFINITION = SkillDefinition(
    id="builtin.product_intro_video",
    version="0.1.0",
    name="Product Intro Video",
    description="Default planning skill for product intro videos.",
    trigger_conditions={
        "runTypes": [
            "initial_planning",
            "user_revision",
            "grounding_replan",
        ]
    },
    prompts={
        "planner": "planner.md",
        "revision": "revision.md",
        "grounding_replan": "grounding_replan.md",
    },
    handler="backend.skills.builtin.product_intro_video.handlers:build_product_intro_planner_request",
)
