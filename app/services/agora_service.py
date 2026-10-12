import time
import logging
from app.config import settings

logger = logging.getLogger("teachsync.agora")


def generate_agora_rtc_token(channel_name: str, uid: int, role: int = 1, expire_time_in_seconds: int = 3600) -> str:
    """
    Generates Agora RTC Token.
    Role 1 = Publisher, Role 2 = Subscriber.
    """
    try:
        from agora_token_builder import RtcTokenBuilder

        current_time = int(time.time())
        privilege_expired_ts = current_time + expire_time_in_seconds

        token = RtcTokenBuilder.buildTokenWithUid(
            settings.AGORA_APP_ID,
            settings.AGORA_APP_CERTIFICATE,
            channel_name,
            uid,
            role,
            privilege_expired_ts
        )
        return token
    except Exception as e:
        logger.warning(f"Agora token builder failed or mock keys used ({e}), returning fallback test token.")
        # Fallback pseudo-token for dev testing if credentials not provided
        return f"agora_mock_token_{channel_name}_{uid}_{int(time.time())}"
