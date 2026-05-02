from typing import Dict
from fastapi import WebSocket


class WSManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, task_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[task_id] = websocket

    def disconnect(self, task_id: str):
        if task_id in self.active_connections:
            del self.active_connections[task_id]

    async def send_progress(self, task_id: str, progress: float, step: str, data: dict = None):
        if task_id in self.active_connections:
            websocket = self.active_connections[task_id]
            await websocket.send_json({
                "progress": progress,
                "step": step,
                "data": data or {}
            })


ws_manager = WSManager()