from __future__ import annotations

from typing import Any, Callable


class LocalToolAdapter:
    def call(self, handler: Callable[..., Any], *, arguments: dict[str, Any] | None = None) -> Any:
        return handler(**(arguments or {}))
