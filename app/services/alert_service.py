from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Alert, User
from .push_service import push_service
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self):
        # 타입별 알림 조건 캐시
        self.alert_cache = {
            "price": defaultdict(list),  # threshold -> [alerts]
            "rsi": defaultdict(list),  # interval -> [alerts]
            "kimchi_premium": [],
            "dominance": [],
            "mvrv": [],
        }
        self.last_trigger_times = {}
        self.min_trigger_interval = 300  # 5분
        self.last_cache_update = None
        self.cache_ttl = timedelta(minutes=5)

    async def create_alert(
        self, session: AsyncSession, user_id: int, alert_data: Dict[str, Any]
    ) -> Alert:
        """새로운 알림 조건 생성"""
        try:
            alert = Alert(
                user_id=user_id,
                type=alert_data["type"],
                symbol=alert_data["symbol"],
                threshold=float(alert_data["threshold"]),
                direction=alert_data["direction"],
                interval=alert_data.get("interval"),
                currency=alert_data.get("currency", "KRW"),
            )
            session.add(alert)
            await session.commit()  # 먼저 commit
            await session.refresh(alert)  # 그 다음 refresh
            return alert
        except Exception as e:
            await session.rollback()  # 에러 발생 시 rollback
            logger.error(f"Failed to create alert: {str(e)}")
            raise

    async def get_active_alerts(self, session: AsyncSession) -> List[Alert]:
        """활성화된 알림 조건 조회"""
        query = select(Alert).where(Alert.is_active == True).join(Alert.user)
        result = await session.execute(query)
        return result.scalars().all()

    async def check_price_alert(
        self, alert: Alert, market_data: Dict[str, Any]
    ) -> bool:
        """가격 알림 조건 체크"""
        current_price = (
            market_data["krw"] if alert.currency == "KRW" else market_data["usd"]
        )

        if alert.direction == "above":
            return current_price > alert.threshold
        return current_price < alert.threshold

    async def check_rsi_alert(self, alert: Alert, current_rsi: float) -> bool:
        """RSI 알림 조건 체크"""
        if alert.direction == "above":
            return current_rsi > alert.threshold
        return current_rsi < alert.threshold

    async def check_premium_alert(self, alert: Alert, current_premium: float) -> bool:
        """김치프리미엄 알림 조건 체크"""
        if alert.direction == "above":
            return current_premium > alert.threshold
        return current_premium < alert.threshold

    async def refresh_cache(self, session: AsyncSession):
        """주기적으로 DB에서 알림 조건 새로고침"""
        if (
            self.last_cache_update
            and datetime.now() - self.last_cache_update < self.cache_ttl
        ):
            return

        # 캐시 초기화
        self.alert_cache = {
            "price": defaultdict(list),
            "rsi": defaultdict(list),
            "kimchi_premium": [],
            "dominance": [],
            "mvrv": [],
        }

        # 활성화된 알림 조건 조회
        alerts = await self.get_active_alerts(session)

        # 타입별로 분류하여 캐시에 저장
        for alert in alerts:
            if alert.type == "price":
                self.alert_cache["price"][alert.threshold].append(alert)
            elif alert.type == "rsi":
                self.alert_cache["rsi"][alert.interval].append(alert)
            elif alert.type == "kimchi_premium":
                self.alert_cache["kimchi_premium"].append(alert)
            elif alert.type == "dominance":
                self.alert_cache["dominance"].append(alert)
            elif alert.type == "mvrv":
                self.alert_cache["mvrv"].append(alert)

        self.last_cache_update = datetime.now()

    async def process_market_data(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """시장 데이터 수신 시 알림 조건 체크"""
        await self.refresh_cache(session)
        current_time = datetime.now()

        # 가격 알림 체크 (임계값 근처 조건만)
        for currency in ["KRW", "USD"]:
            price = market_data["krw"] if currency == "KRW" else market_data["usd"]
            price_range = (price * 0.95, price * 1.05)  # 현재가 ±5% 범위

            for threshold in self.alert_cache["price"]:
                if price_range[0] <= threshold <= price_range[1]:
                    alerts = [
                        a
                        for a in self.alert_cache["price"][threshold]
                        if a.currency == currency
                    ]
                    for alert in alerts:
                        await self.check_and_trigger_alert(session, alert, market_data)

        # RSI 알림 체크 (해당 interval의 조건만)
        for interval, alerts in self.alert_cache["rsi"].items():
            if interval in market_data["rsi"]:
                for alert in alerts:
                    await self.check_and_trigger_alert(session, alert, market_data)

        # 기타 알림 체크
        for alert in self.alert_cache["kimchi_premium"]:
            await self.check_and_trigger_alert(session, alert, market_data)

    async def trigger_alert(self, session: AsyncSession, alert: Alert):
        """알림 발생 시 처리"""
        try:
            alert.triggered_at = datetime.now()
            await session.commit()

            message = self.create_alert_message(alert)

            if alert.user.fcm_token:
                await push_service.send_push_notification(
                    token=alert.user.fcm_token, title="BitNow 알림", body=message
                )

            logger.info(f"Alert triggered: {message}")

        except Exception as e:
            logger.error(f"Failed to trigger alert: {str(e)}")

    def create_alert_message(self, alert: Alert) -> str:
        """알림 메시지 생성"""
        type_map = {"price": "가격", "rsi": "RSI", "kimchi_premium": "김치프리미엄"}
        direction_map = {"above": "이상", "below": "이하"}

        alert_type = type_map.get(alert.type, alert.type)
        direction = direction_map.get(alert.direction, alert.direction)

        message = f"{alert.symbol} {alert_type}이(가) {alert.threshold}{direction}가 되었습니다."
        if alert.type == "rsi":
            message = f"{alert.symbol} {alert.interval} {message}"

        return message


# 싱글톤 인스턴스 생성
alert_service = AlertService()
