import os
from typing import List, Optional
from openai import OpenAI
from backend.models.task import Scene

SYSTEM_PROMPT = "你是一个视频脚本分析专家。请根据用户提供的视频脚本，将其分解成多个场景。每个场景需要包含：1) 场景描述 2) 搜索关键词列表。直接返回场景列表，不要包含其他内容。"


class GPTService:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                raise RuntimeError("OPENAI_API_KEY is not configured")

            # 延迟创建客户端，避免模块导入阶段依赖 OpenAI/httpx 初始化。
            self._client = OpenAI(
                base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
                api_key=api_key,
            )
        return self._client

    async def analyze_script(self, script: str) -> List[Scene]:
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"分析以下视频脚本：\n{script}"},
            ],
            temperature=0.7,
        )

        content = response.choices[0].message.content
        scenes = self._parse_scenes(content)
        return scenes

    def _parse_scenes(self, content: str) -> List[Scene]:
        scenes = []
        lines = content.strip().split("\n")
        scene_id = 1

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            if ". " in line:
                parts = line.split(". ", 1)
                description = parts[1] if len(parts) > 1 else line
            else:
                description = line

            keywords = [w.strip() for w in description.split() if len(w) > 1]

            scenes.append(Scene(id=scene_id, description=description, keywords=keywords))
            scene_id += 1

        return scenes


gpt_service = GPTService()
