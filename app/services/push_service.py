import firebase_admin
from firebase_admin import credentials, messaging
import os
import logging
from dotenv import load_dotenv

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
        """
        단일 기기에 푸시 알림을 전송합니다.
        """
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
            )

            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return response

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")
            return None

    async def send_multicast_notification(self, tokens: list, title: str, body: str):
        """
        여러 기기에 동시에 푸시 알림을 전송합니다.
        """
        try:
            if not self.initialized:
                logger.error("Firebase not initialized")
                return

            message = messaging.MulticastMessage(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                tokens=tokens,
            )

            response = messaging.send_multicast(message)
            logger.info(f"Successfully sent multicast message: {response}")
            return response

        except Exception as e:
            logger.error(f"Error sending multicast push notification: {str(e)}")
            return None


push_service = PushService()
