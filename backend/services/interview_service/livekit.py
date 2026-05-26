"""LiveKit 集成 — 创建房间、生成 token。"""

import uuid

from common.config import settings


class LiveKitService:
    """LiveKit 房间管理 + token 生成。"""

    def __init__(self):
        self.api_key = settings.livekit_api_key
        self.api_secret = settings.livekit_api_secret
        self.url = settings.livekit_url.replace("http://", "ws://").replace("https://", "wss://")

    def create_room_name(self) -> str:
        return f"interview-{uuid.uuid4().hex[:12]}"

    def generate_token(self, room_name: str, participant_name: str = "candidate") -> str:
        """为参与者生成 LiveKit access token。"""
        try:
            from livekit import api

            token = api.AccessToken(api_key=self.api_key, api_secret=self.api_secret)
            token.with_identity(participant_name).with_name(participant_name)
            token.with_grants(api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
            ))
            return token.to_jwt()
        except ImportError:
            return self._mock_token(room_name, participant_name)
        except Exception:
            return self._mock_token(room_name, participant_name)

    def _mock_token(self, room_name: str, participant_name: str) -> str:
        """开发环境降级 token（不可用于真实 LiveKit 服务器）。"""
        import hashlib, time
        payload = f"{room_name}:{participant_name}:{int(time.time())}"
        return f"dev_{hashlib.sha256(payload.encode()).hexdigest()[:32]}"
