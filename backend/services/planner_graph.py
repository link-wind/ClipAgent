from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from backend.services.planner_runtime import get_planner_runtime


class PlanningState(TypedDict, total=False):
    sessionId: str
    brief: str
    status: str
    agentPlan: dict
    executionPlan: dict


def _build_plan_node(state: PlanningState) -> PlanningState:
    runtime = get_planner_runtime()
    agent_plan, execution_plan = runtime.build_plan_from_brief(state["brief"])
    return {
        **state,
        "status": "planning_complete",
        "agentPlan": agent_plan.model_dump(mode="json"),
        "executionPlan": execution_plan.model_dump(mode="json"),
    }


def build_planning_graph():
    graph = StateGraph(PlanningState)
    graph.add_node("build_plan", _build_plan_node)
    graph.add_edge(START, "build_plan")
    graph.add_edge("build_plan", END)
    return graph.compile()


def run_initial_planning(session_id: str, brief: str) -> PlanningState:
    graph = build_planning_graph()
    return graph.invoke({"sessionId": session_id, "brief": brief})
