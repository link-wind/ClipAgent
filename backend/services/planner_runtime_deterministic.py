from backend.services.planner_models import AgentPlan, ExecutionPlan


class DeterministicPlannerRuntime:
    def build_plan_from_brief(self, brief: str) -> tuple[AgentPlan, ExecutionPlan]:
        title = "智能剪辑短片"
        goal = brief.strip() or "生成产品介绍视频"
        plan = AgentPlan(
            title=title,
            goal=goal,
            summary="根据用户 brief 生成的初版计划",
            scenes=[
                {
                    "id": 1,
                    "purpose": "建立产品识别",
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "duration": 6,
                },
                {
                    "id": 2,
                    "purpose": "突出核心卖点",
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "duration": 8,
                },
            ],
        )
        execution = ExecutionPlan(
            title=title,
            targetDuration=30,
            style="快节奏社媒短片",
            scenes=[
                {
                    "id": 1,
                    "description": "开场展示产品主题",
                    "keywords": ["product", "interface"],
                    "searchQuery": "product interface",
                    "duration": 6,
                },
                {
                    "id": 2,
                    "description": "展示重点功能或体验",
                    "keywords": ["feature", "workflow"],
                    "searchQuery": "feature workflow",
                    "duration": 8,
                },
            ],
        )
        return plan, execution
