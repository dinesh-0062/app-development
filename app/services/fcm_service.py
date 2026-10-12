import logging
import os
from typing import Dict, List, Optional
from app.config import settings

logger = logging.getLogger("teachsync.fcm")

_firebase_initialized = False


def init_firebase():
    global _firebase_initialized
    if _firebase_initialized:
        return
    try:
        import firebase_admin
        from firebase_admin import credentials

        if settings.FIREBASE_CREDENTIALS_PATH and os.path.exists(settings.FIREBASE_CREDENTIALS_PATH):
            cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
            firebase_admin.initialize_app(cred)
            _firebase_initialized = True
            logger.info("Firebase Admin initialized successfully.")
        else:
            logger.info("Firebase credentials file not configured. FCM push notifications running in mock mode.")
    except Exception as e:
        logger.warning(f"Firebase Admin initialization skipped: {e}")


async def send_fcm_notification(
    fcm_token: str,
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None
) -> bool:
    init_firebase()
    if not fcm_token:
        return False
    try:
        from firebase_admin import messaging

        message = messaging.Message(
            notification=messaging.Notification(title=title, body=body),
            data=data or {},
            token=fcm_token,
            android=messaging.AndroidConfig(
                priority='high',
                notification=messaging.AndroidNotification(
                    channel_id='teachsync_high_importance',
                    sound='default',
                )
            )
        )
        response = messaging.send(message)
        logger.info(f"FCM Notification sent successfully: {response}")
        return True
    except Exception as e:
        logger.warning(f"FCM Notification send error (mock or config): {e}")
        return False


async def send_fcm_multicast(
    fcm_tokens: List[str],
    title: str,
    body: str,
    data: Optional[Dict[str, str]] = None
) -> int:
    init_firebase()
    if not fcm_tokens:
        return 0
    success_count = 0
    for token in fcm_tokens:
        if await send_fcm_notification(token, title, body, data):
            success_count += 1
    return success_count
