import backend.app.planning.runtime_langchain as _impl
from backend.app.planning.runtime_langchain import (
    COMPACT_INITIAL_PLAN_SYSTEM_PROMPT,
    INITIAL_PLANNER_SYSTEM_PROMPT,
    REVISION_PLANNER_SYSTEM_PROMPT,
    CompactInitialPlanResult,
    LangChainPlannerRuntime as _AppLangChainPlannerRuntime,
    _MISSING_OPEN_ISSUES,
    _RevisionFallbackError,
)

ChatOpenAI = _impl.ChatOpenAI
DeterministicPlannerRuntime = _impl.DeterministicPlannerRuntime
HumanMessage = _impl.HumanMessage
InitialPlanningResult = _impl.InitialPlanningResult
RevisionPlanningResult = _impl.RevisionPlanningResult
RevisionScenePatch = _impl.RevisionScenePatch
SystemMessage = _impl.SystemMessage
json = _impl.json
openai = _impl.openai
runtime_config_service = _impl.runtime_config_service


def _sync_patchable_exports() -> None:
    _impl.ChatOpenAI = ChatOpenAI
    _impl.DeterministicPlannerRuntime = DeterministicPlannerRuntime
    _impl.HumanMessage = HumanMessage
    _impl.InitialPlanningResult = InitialPlanningResult
    _impl.RevisionPlanningResult = RevisionPlanningResult
    _impl.RevisionScenePatch = RevisionScenePatch
    _impl.SystemMessage = SystemMessage
    _impl.json = json
    _impl.openai = openai
    _impl.runtime_config_service = runtime_config_service


class LangChainPlannerRuntime(_AppLangChainPlannerRuntime):
    def __init__(self, *args, **kwargs):
        _sync_patchable_exports()
        super().__init__(*args, **kwargs)


__all__ = [
    "COMPACT_INITIAL_PLAN_SYSTEM_PROMPT",
    "ChatOpenAI",
    "CompactInitialPlanResult",
    "DeterministicPlannerRuntime",
    "HumanMessage",
    "INITIAL_PLANNER_SYSTEM_PROMPT",
    "InitialPlanningResult",
    "LangChainPlannerRuntime",
    "REVISION_PLANNER_SYSTEM_PROMPT",
    "RevisionPlanningResult",
    "RevisionScenePatch",
    "SystemMessage",
    "_MISSING_OPEN_ISSUES",
    "_RevisionFallbackError",
    "json",
    "openai",
    "runtime_config_service",
]
