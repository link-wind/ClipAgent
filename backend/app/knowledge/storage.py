from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SavedKnowledgeUpload:
    storage_path: str
    file_size: int


class LocalKnowledgeStorage:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_upload(
        self,
        *,
        project_key: str,
        source_id: str,
        version_number: int,
        filename: str,
        content: bytes,
    ) -> SavedKnowledgeUpload:
        safe_filename = Path(filename).name
        relative = Path(project_key) / source_id / f"v{version_number}" / safe_filename
        target = self.root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return SavedKnowledgeUpload(storage_path=str(relative), file_size=len(content))

    def open(self, storage_path: str):
        return (self.root / storage_path).open("rb")

    def delete(self, storage_path: str) -> None:
        target = self.root / storage_path
        if target.exists():
            target.unlink()

    def exists(self, storage_path: str) -> bool:
        return (self.root / storage_path).exists()
