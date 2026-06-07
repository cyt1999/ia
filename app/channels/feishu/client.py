import json
import time

import httpx

from app.config.settings import Settings


class FeishuClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tenant_token: str | None = None
        self._tenant_token_expires_at = 0.0

    async def tenant_access_token(self) -> str:
        if self._tenant_token and time.time() < self._tenant_token_expires_at - 60:
            return self._tenant_token
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
                json={
                    "app_id": self.settings.feishu_app_id,
                    "app_secret": self.settings.feishu_app_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
        self._tenant_token = data["tenant_access_token"]
        self._tenant_token_expires_at = time.time() + int(data.get("expire", 7200))
        return self._tenant_token

    async def send_message(self, receive_id: str, msg_type: str, content: dict) -> str | None:
        token = await self.tenant_access_token()
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                "https://open.feishu.cn/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": json.dumps(content, ensure_ascii=False),
                },
            )
            response.raise_for_status()
            data = response.json()
        return data.get("data", {}).get("message_id")
