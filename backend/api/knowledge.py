from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from backend.app.knowledge.source_delete_service import KnowledgeSourceDeleteService
from backend.app.knowledge.source_read_service import KnowledgeSourceReadService
from backend.app.knowledge.upload_service import KnowledgeUploadService
from backend.db import SessionLocal
from backend.models.knowledge import KnowledgeSourceSummary


router = APIRouter()


def _validate_upload_filename(filename: str) -> str:
    normalized = (filename or "").strip()
    if not normalized.endswith((".txt", ".md")):
        raise HTTPException(status_code=400, detail="Only .txt and .md uploads are supported")
    return normalized


@router.post("/knowledge-sources/upload", response_model=KnowledgeSourceSummary)
async def upload_knowledge_source(file: UploadFile = File(...)):
    filename = _validate_upload_filename(file.filename or "")
    content = await file.read()

    def _upload():
        with SessionLocal() as db:
            service = KnowledgeUploadService(db)
            return service.upload_file(
                filename=filename,
                content=content,
                content_type=file.content_type,
            )

    try:
        return await run_in_threadpool(_upload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/knowledge-sources/{source_id}", response_model=KnowledgeSourceSummary)
async def get_knowledge_source(source_id: str):
    try:
        read_service = KnowledgeSourceReadService(session_factory=SessionLocal)
        return await run_in_threadpool(read_service.get_summary, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Knowledge source not found")


@router.delete("/knowledge-sources/{source_id}", response_model=KnowledgeSourceSummary)
async def delete_knowledge_source(source_id: str):
    try:
        delete_service = KnowledgeSourceDeleteService(session_factory=SessionLocal)
        return await run_in_threadpool(delete_service.delete_source, source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Knowledge source not found")
