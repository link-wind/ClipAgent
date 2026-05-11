from typing import Any

from backend.models.agent import AgentDiagnostic


STEP_TO_PHASE = {
    "planning": "planning",
    "finalize_plan": "planning",
    "searching": "search_assets",
    "search_assets": "search_assets",
    "downloading": "prepare_assets",
    "prepare_assets": "prepare_assets",
    "rendering": "render_video",
    "render_video": "render_video",
}

SUPPORTED_CATEGORIES = {
    "no_inventory",
    "provider_blocked",
    "download_failed",
    "render_failed",
    "planning_failed",
    "unknown",
}

PROVIDER_LABELS = {
    "pexels": "Pexels",
    "youtube": "YouTube",
}


class AgentDiagnosticService:
    def build_diagnostic(self, *, session_record=None, job_record=None, event_rows=None) -> AgentDiagnostic | None:
        payload = self._latest_failure_payload(event_rows or [])
        message = self._resolve_message(payload, session_record, job_record)
        if not message:
            return None

        phase = self._resolve_phase(payload, session_record, job_record)
        category = self._resolve_category(payload, phase, message)
        failed_scene_ids = self._normalize_scene_ids(payload.get("failedSceneIds"))
        primary_provider = self._normalize_optional_string(payload.get("primaryProvider"))
        provider_diagnostics = self._normalize_record_list(payload.get("providerDiagnostics"))
        scene_diagnostics = self._normalize_record_list(payload.get("sceneDiagnostics"))
        retry_strategy_hint = self._normalize_optional_string(payload.get("retryStrategyHint"))

        return AgentDiagnostic(
            phase=phase,
            category=category,
            title=self._build_title(category, phase),
            message=self._build_message(
                raw_message=message,
                primary_provider=primary_provider,
                failed_scene_ids=failed_scene_ids,
            ),
            primaryProvider=primary_provider,
            failedSceneIds=failed_scene_ids,
            providerDiagnostics=provider_diagnostics,
            sceneDiagnostics=scene_diagnostics,
            retryStrategyHint=retry_strategy_hint,
            repairPrompt=self._build_repair_prompt(
                message=message,
                phase=phase,
                category=category,
                primary_provider=primary_provider,
                failed_scene_ids=failed_scene_ids,
            ),
            severity="error",
        )

    def _latest_failure_payload(self, event_rows) -> dict[str, Any]:
        for row in reversed(list(event_rows)):
            if getattr(row, "event_type", "") != "job_failed":
                continue
            payload = getattr(row, "payload_json", None) or {}
            if isinstance(payload, dict):
                return payload
        return {}

    def _resolve_message(self, payload: dict[str, Any], session_record, job_record) -> str:
        for value in (
            payload.get("failureReason"),
            payload.get("message"),
            getattr(job_record, "error_message", None),
            getattr(session_record, "error_message", None),
        ):
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _resolve_phase(self, payload: dict[str, Any], session_record, job_record) -> str:
        for value in (
            payload.get("retryableStep"),
            getattr(session_record, "error_retryable_step", None),
            getattr(job_record, "current_step", None),
        ):
            phase = self._phase_from_value(value)
            if phase != "unknown":
                return phase
        return "unknown"

    def _phase_from_value(self, value) -> str:
        if not isinstance(value, str):
            return "unknown"
        if value in STEP_TO_PHASE:
            return STEP_TO_PHASE[value]
        if "素材" in value or "搜索" in value:
            return "search_assets"
        if "渲染" in value or "合成" in value:
            return "render_video"
        return "unknown"

    def _resolve_category(self, payload: dict[str, Any], phase: str, message: str) -> str:
        category = payload.get("failureCategory")
        if isinstance(category, str) and category in SUPPORTED_CATEGORIES:
            return category

        lowered = message.lower()
        if any(token in lowered for token in ("403", "blocked", "rate limit", "unauthorized", "forbidden")):
            return "provider_blocked"
        if phase == "render_video":
            return "render_failed"
        if phase == "planning":
            return "planning_failed"
        return "unknown"

    def _build_title(self, category: str, phase: str) -> str:
        if category == "no_inventory":
            return "素材搜索没有找到可用结果"
        if category == "provider_blocked":
            return "外部素材源暂时不可用"
        if category == "download_failed":
            return "素材下载失败"
        if category == "render_failed":
            return "视频渲染失败"
        if category == "planning_failed":
            return "方案规划失败"
        if phase == "search_assets":
            return "素材搜索失败"
        return "任务执行失败"

    def _build_message(self, *, raw_message: str, primary_provider: str | None, failed_scene_ids: list[int]) -> str:
        parts: list[str] = []
        if primary_provider:
            parts.append(self._provider_label(primary_provider))
        if failed_scene_ids:
            parts.append(self._scene_label(failed_scene_ids))
        if parts:
            return f"{' / '.join(parts)}：{raw_message}"
        return raw_message

    def _build_repair_prompt(
        self,
        *,
        message: str,
        phase: str,
        category: str,
        primary_provider: str | None,
        failed_scene_ids: list[int],
    ) -> str:
        context_parts: list[str] = []
        if failed_scene_ids:
            context_parts.append(self._scene_label(failed_scene_ids))
        if primary_provider:
            context_parts.append(f"{self._provider_label(primary_provider)} 素材源")
        context = " / ".join(context_parts)
        prefix = f"{context}：{message}" if context else message

        if phase == "search_assets" or category in {"no_inventory", "provider_blocked"}:
            return f"请根据这次失败调整方案：{prefix}。请放宽检索关键词，优先选择更通用、容易找到真实素材的画面方向，并保持总时长不变。"
        if phase == "render_video":
            return f"请根据这次失败调整方案：{prefix}。请简化镜头结构，减少对特殊素材或复杂渲染的依赖，并保持总时长不变。"
        return f"请根据这次失败调整方案：{prefix}。请保持原始目标不变，改写为更容易执行的方案。"

    def _normalize_scene_ids(self, value) -> list[int]:
        if not isinstance(value, list):
            return []
        scene_ids: list[int] = []
        for item in value:
            if isinstance(item, int) and item not in scene_ids:
                scene_ids.append(item)
        return scene_ids

    def _normalize_record_list(self, value) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _normalize_optional_string(self, value) -> str | None:
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def _provider_label(self, provider: str) -> str:
        return PROVIDER_LABELS.get(provider.lower(), provider)

    def _scene_label(self, scene_ids: list[int]) -> str:
        return "、".join(f"场景 {scene_id}" for scene_id in scene_ids)
