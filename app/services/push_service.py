import json
import aiohttp
from typing import Dict, Any
import logging
from app.constants import FCM_SERVER_KEY

logger = logging.getLogger(__name__)


class PushService:
    def __init__(self):
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.headers = {
            "Authorization": f"key={FCM_SERVER_KEY}",
            "Content-Type": "application/json",
        }

    async def send_push_notification(self, token: str, title: str, body: str):
        """FCM 푸시 알림 전송"""
        try:
            payload = {
                "to": token,
                "notification": {"title": title, "body": body, "sound": "default"},
            }

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.fcm_url, headers=self.headers, json=payload
                ) as response:
                    if response.status == 200:
                        logger.info(f"Push notification sent successfully to {token}")
                    else:
                        logger.error(
                            f"Failed to send push notification: {response.status}"
                        )

        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}")


# 싱글톰 인스턴스 생성
push_service = PushService()
