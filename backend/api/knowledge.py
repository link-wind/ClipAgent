from fastapi import APIRouter, File, HTTPException, UploadFile


router = APIRouter()


@router.post("/knowledge-sources/upload")
async def upload_knowledge_source(file: UploadFile = File(...)):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.get("/knowledge-sources/{source_id}")
async def get_knowledge_source(source_id: str):
    raise HTTPException(status_code=501, detail="Not implemented")


@router.delete("/knowledge-sources/{source_id}")
async def delete_knowledge_source(source_id: str):
    raise HTTPException(status_code=501, detail="Not implemented")
