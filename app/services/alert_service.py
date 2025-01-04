from typing import Dict, Any, List
from datetime import datetime, timedelta
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Alert, User
from .push_service import push_service
from collections import defaultdict
from sqlalchemy.orm import joinedload
from sqlalchemy import update
import aiohttp

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
                is_active=True,  # 명시적으로 is_active 설정
            )
            session.add(alert)
            await session.commit()  # 먼저 commit
            await session.refresh(alert)  # 그 다음 refresh

            # 새 알림 생성 시 캐시 즉시 갱신
            self.last_cache_update = None  # 캐시 TTL 초기화
            await self.refresh_cache(session)
            logger.info(f"Created new alert and refreshed cache: {alert.id}")

            # 현재 시장 데이터로 즉시 알림 조건 체크
            current_market_data = {
                "krw": 0.0,
                "usd": 0.0,
                "timestamp": datetime.now().isoformat(),
                "kimchi_premium": 0.0,
                "rsi": {},
            }

            # 현재 가격 조회
            if alert.type == "price":
                try:
                    if alert.currency == "KRW":
                        async with aiohttp.ClientSession() as client:
                            async with client.get(
                                "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    current_market_data["krw"] = float(
                                        data[0]["trade_price"]
                                    )
                    else:  # USD
                        async with aiohttp.ClientSession() as client:
                            async with client.get(
                                "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
                            ) as response:
                                if response.status == 200:
                                    data = await response.json()
                                    current_market_data["usd"] = float(data["price"])

                    # 새로 생성된 알림 조건 즉시 체크
                    await self.process_market_data(session, current_market_data)
                    logger.info(
                        f"Checked new alert {alert.id} with current market data"
                    )
                except Exception as e:
                    logger.error(f"Failed to check new alert condition: {str(e)}")

            return alert
        except Exception as e:
            await session.rollback()  # 에러 발생 시 rollback
            logger.error(f"Failed to create alert: {str(e)}")
            raise

    async def get_active_alerts(self, session: AsyncSession) -> List[Alert]:
        """활성화된 알림 조건 조회"""
        query = select(Alert).where(Alert.is_active == True).join(Alert.user)
        result = await session.execute(query)
        alerts = result.scalars().all()
        logger.debug(f"Found {len(alerts)} active alerts in database")
        for alert in alerts:
            logger.debug(
                f"Active alert: ID={alert.id}, Type={alert.type}, Is_active={alert.is_active}"
            )
        return alerts

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
        try:
            # TTL 체크를 더 엄격하게 수정
            current_time = datetime.now()
            if (
                self.last_cache_update
                and (current_time - self.last_cache_update) < self.cache_ttl
                and self.alert_cache["price"]  # 캐시가 비어있지 않은지 확인
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
            logger.info(f"Refreshing cache with {len(alerts)} active alerts")

            # 타입별로 분류하여 캐시에 저장
            for alert in alerts:
                if alert.type == "price":
                    self.alert_cache["price"][alert.threshold].append(alert)
                    logger.debug(
                        f"Added price alert: {alert.id}, threshold: {alert.threshold}"
                    )
                elif alert.type == "rsi":
                    self.alert_cache["rsi"][alert.interval].append(alert)
                    logger.debug(
                        f"Added RSI alert: {alert.id}, interval: {alert.interval}"
                    )
                elif alert.type == "kimchi_premium":
                    self.alert_cache["kimchi_premium"].append(alert)
                    logger.debug(f"Added kimchi premium alert: {alert.id}")

            self.last_cache_update = current_time
            logger.debug(f"Cache refresh completed with {len(alerts)} total alerts")

        except Exception as e:
            logger.error(f"Error refreshing cache: {str(e)}")
            logger.exception(e)

    async def process_market_data(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """시장 데이터 수신 시 알림 조건 체크"""
        try:
            await self.refresh_cache(session)

            # 가격 알림 체크
            for currency in ["KRW", "USD"]:
                price = market_data["krw"] if currency == "KRW" else market_data["usd"]
                logger.debug(
                    f"Checking price alerts for {currency}. Current price: {price}"
                )

                # 모든 가격 알림 조건을 체크
                for threshold in self.alert_cache["price"]:
                    alerts = [
                        a
                        for a in self.alert_cache["price"][threshold]
                        if a.currency == currency and a.is_active  # is_active 체크 추가
                    ]

                    if alerts:
                        logger.debug(
                            f"Found {len(alerts)} active alerts for threshold {threshold}"
                        )

                    for alert in alerts:
                        should_trigger = await self.check_price_alert(
                            alert, market_data
                        )
                        logger.debug(
                            f"Alert {alert.id} (threshold: {alert.threshold}, direction: {alert.direction}) should trigger: {should_trigger}"
                        )

                        if should_trigger:
                            logger.info(
                                f"Price alert triggered: {alert.id}, Current Price: {price}, Threshold: {alert.threshold}, Direction: {alert.direction}"
                            )
                            await self.trigger_alert(session, alert)

            # RSI 알림 체크
            for interval, alerts in self.alert_cache["rsi"].items():
                if interval in market_data.get("rsi", {}):
                    current_rsi = market_data["rsi"][interval]
                    logger.debug(
                        f"Checking RSI alerts for {interval}. Current RSI: {current_rsi}"
                    )

                    for alert in alerts:
                        should_trigger = await self.check_rsi_alert(alert, current_rsi)
                        logger.debug(
                            f"RSI Alert {alert.id} should trigger: {should_trigger}"
                        )

                        if should_trigger:
                            logger.info(
                                f"RSI alert triggered: {alert.id}, RSI: {current_rsi}"
                            )
                            await self.trigger_alert(session, alert)

            # 김치프리미엄 알림 체크
            if "kimchi_premium" in market_data:
                current_premium = market_data["kimchi_premium"]
                logger.debug(
                    f"Checking premium alerts. Current premium: {current_premium}"
                )

                for alert in self.alert_cache["kimchi_premium"]:
                    should_trigger = await self.check_premium_alert(
                        alert, current_premium
                    )
                    logger.debug(
                        f"Premium Alert {alert.id} should trigger: {should_trigger}"
                    )

                    if should_trigger:
                        logger.info(
                            f"Premium alert triggered: {alert.id}, Premium: {current_premium}"
                        )
                        await self.trigger_alert(session, alert)

        except Exception as e:
            logger.error(f"Error in process_market_data: {str(e)}")
            logger.exception(e)

    async def trigger_alert(self, session: AsyncSession, alert: Alert):
        """알림 발생 시 처리"""
        try:
            # Alert 객체와 연관된 User 객체를 함께 로드
            stmt = (
                select(Alert)
                .options(joinedload(Alert.user))
                .where(Alert.id == alert.id)
            )
            result = await session.execute(stmt)
            alert_with_user = result.unique().scalar_one()

            # 알림 발생 시간 업데이트 및 비활성화
            update_stmt = (
                update(Alert)
                .where(Alert.id == alert.id)
                .values(
                    triggered_at=datetime.now(),
                    is_active=False,
                    updated_at=datetime.now(),
                )
            )
            await session.execute(update_stmt)
            await session.commit()

            # 알림 비활성화 후 캐시 즉시 갱신
            self.last_cache_update = None
            await self.refresh_cache(session)
            logger.info(f"Alert {alert.id} deactivated and cache refreshed")

            message = self.create_alert_message(alert_with_user)

            if alert_with_user.user and alert_with_user.user.fcm_token:
                await push_service.send_push_notification(
                    token=alert_with_user.user.fcm_token,
                    title="BitNow 알림",
                    body=message,
                )
                logger.info(f"Alert triggered and notification sent: {message}")
                logger.debug(
                    f"Alert {alert_with_user.id} deactivated (is_active=False)"
                )
            else:
                logger.warning(
                    f"User has no FCM token for alert ID: {alert_with_user.id}"
                )

        except Exception as e:
            logger.error(f"Failed to trigger alert: {str(e)}")
            logger.exception(e)

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

    async def check_and_trigger_alert(
        self, session: AsyncSession, alert: Alert, market_data: Dict[str, Any]
    ):
        """알림 조건을 체크하고 조건 충족 시 알림을 트리거합니다."""
        try:
            # 마지막 트리거 시간 체크
            last_trigger = self.last_trigger_times.get(alert.id)
            if (
                last_trigger
                and (datetime.now() - last_trigger).total_seconds()
                < self.min_trigger_interval
            ):
                return

            should_trigger = False

            # 알림 타입별 체크
            if alert.type == "price":
                should_trigger = await self.check_price_alert(alert, market_data)
            elif alert.type == "rsi" and alert.interval in market_data["rsi"]:
                should_trigger = await self.check_rsi_alert(
                    alert, market_data["rsi"][alert.interval]
                )
            elif alert.type == "kimchi_premium":
                should_trigger = await self.check_premium_alert(
                    alert, market_data["kimchi_premium"]
                )

            # 조건 충족 시 알림 트리거
            if should_trigger:
                await self.trigger_alert(session, alert)
                self.last_trigger_times[alert.id] = datetime.now()

        except Exception as e:
            logger.error(f"알림 체크 중 오류 발생: {str(e)}")

    async def get_all_alerts(self, session: AsyncSession) -> List[Alert]:
        """모든 알림 조건 조회 (비활성화된 알림 포함)"""
        query = select(Alert).join(Alert.user)
        result = await session.execute(query)
        alerts = result.scalars().all()
        logger.debug(f"Found {len(alerts)} total alerts in database")
        return alerts


# 싱글톤 인스턴스 생성
alert_service = AlertService()
