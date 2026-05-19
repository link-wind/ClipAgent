from typing import Any

_CLIP_METADATA_BY_LOCAL_PATH: dict[str, dict[str, Any]] = {}


def remember_clip_metadata(local_path: str, metadata: dict[str, Any]) -> None:
    if not local_path or not metadata:
        return
    _CLIP_METADATA_BY_LOCAL_PATH[local_path] = dict(metadata)


def pop_clip_metadata(local_path: str) -> dict[str, Any]:
    if not local_path:
        return {}
    return _CLIP_METADATA_BY_LOCAL_PATH.pop(local_path, {})
