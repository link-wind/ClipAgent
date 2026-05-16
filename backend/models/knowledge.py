from pydantic import BaseModel


class KnowledgeVersionSummary(BaseModel):
    id: str
    versionNumber: int
    contentHash: str
    status: str
    createdAt: str
    updatedAt: str
    failedAt: str | None = None
    reason: str | None = None


class KnowledgeSourceSummary(BaseModel):
    id: str
    name: str
    status: str
    contentType: str
    createdAt: str
    updatedAt: str
    errorSummary: str | None = None
    activeVersion: KnowledgeVersionSummary | None = None
    processingVersion: KnowledgeVersionSummary | None = None
    lastFailedVersion: KnowledgeVersionSummary | None = None
    deletionRequestedAt: str | None = None
