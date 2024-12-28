from typing import Dict, Any, List
from datetime import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Alert, User
from .push_service import push_service

logger = logging.getLogger(__name__)


class AlertService:
    def __init__(self):
        self.last_trigger_times: Dict[int, datetime] = {}
        self.min_trigger_interval = 300

    async def create_alert(
        self, session: AsyncSession, user_id: int, alert_data: Dict[str, Any]
    ) -> Alert:
        """새로운 알림 조건 생성"""
        alert = Alert(
            user_id=user_id,
            type=alert_data["type"],
            symbol=alert_data["symbol"],
            threshold=float(alert_data["threshold"]),
            direction=alert_data["direction"],
            interval=alert_data.get("interval"),
        )
        session.add(alert)
        await session.commit()
        await session.refresh(alert)
        return alert

    async def get_active_alerts(self, session: AsyncSession) -> List[Alert]:
        """활성화된 알림 조건 조회"""
        query = select(Alert).where(Alert.is_active == True).join(Alert.user)
        result = await session.execute(query)
        return result.scalars().all()

    async def check_price_alert(self, alert: Alert, current_price: float) -> bool:
        """가격 알림 조건 체크"""
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

    async def process_market_data(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """시장 데이터 수신 시 알림 조건 체크"""
        alerts = await self.get_active_alerts(session)
        current_time = datetime.now()

        for alert in alerts:
            if (
                self.last_trigger_times.get(alert.id)
                and (current_time - self.last_trigger_times[alert.id]).total_seconds()
                < self.min_trigger_interval
            ):
                continue

            triggered = False
            if alert.type == "price" and alert.symbol == "BTC":
                triggered = await self.check_price_alert(alert, market_data["krw"])
            elif alert.type == "rsi" and alert.interval in market_data["rsi"]:
                triggered = await self.check_rsi_alert(
                    alert, market_data["rsi"][alert.interval]
                )
            elif alert.type == "kimchi_premium":
                triggered = await self.check_premium_alert(
                    alert, market_data["kimchi_premium"]
                )

            if triggered:
                self.last_trigger_times[alert.id] = current_time
                await self.trigger_alert(session, alert)

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
