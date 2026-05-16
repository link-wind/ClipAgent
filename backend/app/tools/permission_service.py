from __future__ import annotations

from dataclasses import dataclass

from backend.domain.tools.contracts import ToolPermission


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    reason: str = ""


class ToolPermissionService:
    def decide(self, permission: ToolPermission, requested_scope: str) -> PermissionDecision:
        if permission.mode != "read_only":
            return PermissionDecision(allowed=False, reason=f"unsupported mode: {permission.mode}")
        if permission.scope != requested_scope:
            return PermissionDecision(
                allowed=False,
                reason=f"scope mismatch: required {permission.scope}, requested {requested_scope}",
            )
        return PermissionDecision(allowed=True, reason="allowed")
