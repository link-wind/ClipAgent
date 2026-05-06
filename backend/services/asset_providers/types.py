from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ProviderDiagnostic:
    provider: str
    phase: str
    message: str
    retryable: bool = True

    def to_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "phase": self.phase,
            "message": self.message,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class AssetCandidate:
    provider: str
    id: str
    title: str
    source_url: str
    download_url: str = ""
    duration: float = 0.0
    width: int | None = None
    height: int | None = None
    thumbnail: str = ""
    author: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_legacy_video_info(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "url": self.source_url,
            "duration": self.duration,
            "thumbnail": self.thumbnail,
            "provider": self.provider,
            "downloadUrl": self.download_url,
            "author": self.author,
            "diagnostics": self.diagnostics,
        }

    def to_metadata(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "provider": self.provider,
            "providerId": self.id,
            "title": self.title,
            "sourceUrl": self.source_url,
        }
        if self.download_url:
            metadata["downloadUrl"] = self.download_url
        if self.width is not None:
            metadata["width"] = self.width
        if self.height is not None:
            metadata["height"] = self.height
        if self.thumbnail:
            metadata["thumbnail"] = self.thumbnail
        if self.author:
            metadata["author"] = self.author
        if self.diagnostics:
            metadata["diagnostics"] = self.diagnostics
        return metadata


@dataclass(frozen=True)
class AssetDownload:
    local_path: str
    public_url: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResult:
    provider: str
    candidates: list[AssetCandidate] = field(default_factory=list)
    diagnostics: list[ProviderDiagnostic] = field(default_factory=list)
