import firebase_admin
from firebase_admin import credentials, messaging
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FirebaseService:
    def __init__(self):
        self.initialized = False
        self.initialize()

    def initialize(self):
        try:
            # Firebase 인증 정보 설정
            # Railway에서는 환경 변수로 Firebase 인증 정보를 설정할 수 있습니다
            firebase_cred_path = os.getenv(
                "FIREBASE_CREDENTIALS", "firebase-adminsdk.json"
            )

            # 환경 변수에서 직접 JSON 문자열을 가져오는 경우
            firebase_cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

            if firebase_cred_json:
                # JSON 문자열을 딕셔너리로 변환하여 사용
                cred_dict = json.loads(firebase_cred_json)
                cred = credentials.Certificate(cred_dict)
            elif os.path.exists(firebase_cred_path):
                # 파일에서 인증 정보 로드
                cred = credentials.Certificate(firebase_cred_path)
            else:
                logger.error(f"Firebase credentials not found at {firebase_cred_path}")
                return

            firebase_admin.initialize_app(cred)
            self.initialized = True
            logger.info("Firebase service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
            self.initialized = False

    def send_push_notification(self, token, title, body, data=None):
        """
        FCM을 통해 푸시 알림을 전송합니다.

        Args:
            token (str): 디바이스 토큰
            title (str): 알림 제목
            body (str): 알림 내용
            data (dict, optional): 추가 데이터

        Returns:
            bool: 전송 성공 여부
        """
        if not self.initialized:
            logger.error("Firebase service not initialized")
            return False

        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body,
                ),
                data=data or {},
                token=token,
            )

            response = messaging.send(message)
            logger.info(f"Successfully sent message: {response}")
            return True
        except Exception as e:
            logger.error(f"Failed to send push notification: {str(e)}")
            return False


# 싱글톤 인스턴스 생성
firebase_service = FirebaseService()
