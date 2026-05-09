from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.services.planner_models import (
    AgentPlan,
    CandidateConfirmationFeedback,
    ExecutionPlan,
    GroundingFeedback,
)
from backend.services.planner_runtime import get_planner_runtime


class PlanningState(TypedDict, total=False):
    sessionId: str
    brief: str
    status: str
    triggerType: str
    agentPlan: dict
    executionPlan: dict
    groundingFeedback: dict
    confirmationFeedback: dict
    changeSummary: str


def _build_plan_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    agent_plan, execution_plan = runtime.build_plan_from_brief(state["brief"])
    return {
        **state,
        "status": "planning_complete",
        "agentPlan": agent_plan.model_dump(mode="json"),
        "executionPlan": execution_plan.model_dump(mode="json"),
    }


def _replan_after_grounding_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    current_agent = AgentPlan.model_validate(state["agentPlan"])
    current_execution = ExecutionPlan.model_validate(state["executionPlan"])
    next_agent, next_execution, change_summary = runtime.replan_after_grounding(
        current_agent=current_agent,
        current_execution=current_execution,
        grounding_feedback=GroundingFeedback.model_validate(state["groundingFeedback"]),
        confirmation_feedback=CandidateConfirmationFeedback.model_validate(
            state["confirmationFeedback"]
        ),
    )
    return {
        **state,
        "status": "replanning_complete",
        "triggerType": "grounding_confirmation",
        "agentPlan": next_agent.model_dump(mode="json"),
        "executionPlan": next_execution.model_dump(mode="json"),
        "changeSummary": change_summary,
    }


def build_planning_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("build_plan", _build_plan_node)
    graph.add_edge(START, "build_plan")
    graph.add_edge("build_plan", END)
    return graph.compile()


def build_grounding_replan_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("replan_after_grounding", _replan_after_grounding_node)
    graph.add_edge(START, "replan_after_grounding")
    graph.add_edge("replan_after_grounding", END)
    return graph.compile()


def run_initial_planning(session_id: str, brief: str) -> PlanningState:
    graph = build_planning_graph()
    return graph.invoke({"sessionId": session_id, "brief": brief})


def run_grounding_replan(
    session_id: str,
    current_agent_plan: dict,
    current_execution_plan: dict,
    grounding_feedback: dict,
    confirmation_feedback: dict,
) -> PlanningState:
    graph = build_grounding_replan_graph()
    return graph.invoke(
        {
            "sessionId": session_id,
            "status": "replanning",
            "triggerType": "grounding_confirmation",
            "agentPlan": current_agent_plan,
            "executionPlan": current_execution_plan,
            "groundingFeedback": grounding_feedback,
            "confirmationFeedback": confirmation_feedback,
        }
    )
