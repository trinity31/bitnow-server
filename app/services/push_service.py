import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging
from dotenv import load_dotenv
import asyncio

load_dotenv()
logger = logging.getLogger(__name__)


class PushService:
    def __init__(self):
        self.initialized = False
        self.initialize_firebase()

    def initialize_firebase(self):
        try:
            if not self.initialized:
                cred_path = os.getenv("FIREBASE_CREDENTIALS")
                if cred_path:
                    cred = credentials.Certificate(cred_path)
                    firebase_admin.initialize_app(cred)
                    self.initialized = True
                    logger.info("Firebase Admin SDK initialized successfully")
                else:
                    logger.warning(
                        "FIREBASE_CREDENTIALS not found in environment variables"
                    )
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")

    async def send_push_notification(self, token: str, title: str, body: str):
        """단일 기기에 푸시 알림을 전송합니다."""
        try:
            if not self.initialized:
                logger.error("Firebase not initialized")
                return

            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                token=token,
                android=messaging.AndroidConfig(
                    notification=messaging.AndroidNotification(
                        channel_id="default_channel_id",
                        sound="default",  # Android 알림음
                    )
                ),
                apns=messaging.APNSConfig(  # iOS 알림음 설정 추가
                    payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
                ),
                data={
                    "click_action": "FLUTTER_NOTIFICATION_CLICK",
                    "type": "price_alert",
                },
            )
            # 동기 함수를 별도 스레드에서 실행
            response = await asyncio.to_thread(messaging.send, message)
            logger.info(f"Successfully sent message: {response}")
            return response

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            logger.exception(e)
            return None


push_service = PushService()
