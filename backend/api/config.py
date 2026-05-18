from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.infrastructure.config.runtime_config_service import RuntimeConfigService, runtime_config_service


class SettingsUpdateRequest(BaseModel):
    updates: dict[str, Any] = Field(default_factory=dict)


class SettingsClearRequest(BaseModel):
    keys: list[str] = Field(default_factory=list)


def create_config_router(service: RuntimeConfigService = runtime_config_service) -> APIRouter:
    router = APIRouter()

    @router.get("/settings")
    async def get_settings():
        try:
            return service.get_settings_response()
        except ValueError as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc

    @router.patch("/settings")
    async def update_settings(request: SettingsUpdateRequest):
        try:
            return service.update(request.updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/settings/clear")
    async def clear_settings(request: SettingsClearRequest):
        try:
            return service.clear(request.keys)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return router


router = create_config_router()
