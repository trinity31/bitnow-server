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
import asyncio  # 락 사용을 위해 필요
from app.constants import BATCH_CREATE_THRESHOLD
import time

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
        # batch_create_count 를 동적으로 관리 (초기값 0)
        self.batch_create_count = 0
        self.trigger_lock = asyncio.Lock()  # 알림 트리거 동시성 방지용 락

        # 통화(currency)별로 마지막으로 본 가격 저장
        self.last_price_by_currency = {"KRW": None, "USD": None}
        # RSI 마지막 값 저장용 딕셔너리 추가
        self.last_rsi_by_interval = defaultdict(lambda: None)  # interval -> last_rsi
        self.last_rsi_check = {}  # 각 interval별 마지막 RSI 체크 시간
        self.rsi_check_interval = 60  # RSI 체크 간격 (초)

    async def create_alert(
        self, session: AsyncSession, user_id: int, alert_data: Dict[str, Any]
    ) -> Alert:
        """새로운 알림 조건 생성"""
        try:
            # 알림 타입 검증
            valid_types = ["price", "rsi", "kimchi_premium", "dominance", "mvrv"]
            if alert_data["type"].lower() not in valid_types:
                raise ValueError(
                    f"유효하지 않은 알림 타입입니다. ({', '.join(valid_types)})"
                )

            # RSI 알림인 경우 interval 필수 체크
            if alert_data["type"].upper() == "RSI":
                if not alert_data.get("interval") or alert_data["interval"] not in [
                    "15m",
                    "1h",
                    "4h",
                    "1d",
                ]:
                    raise ValueError(
                        "RSI 알림은 interval이 필수입니다. (15m, 1h, 4h, 1d 중 하나)"
                    )

            alert = Alert(
                user_id=user_id,
                type=alert_data["type"].lower(),  # 소문자로 저장
                symbol=alert_data["symbol"],
                threshold=float(alert_data["threshold"]),
                direction=alert_data["direction"],
                interval=alert_data.get("interval"),
                currency=alert_data.get("currency", "KRW"),
                is_active=True,
            )
            session.add(alert)
            await session.commit()
            await session.refresh(alert)

            # 현재 batch_create_count 증가
            self.batch_create_count += 1

            # BATCH_CREATE_THRESHOLD만큼 누적되었을 때만 캐시 갱신
            if self.batch_create_count >= BATCH_CREATE_THRESHOLD:
                self.last_cache_update = None
                await self.refresh_cache(session)
                logger.info(
                    f"Batch create threshold reached. "
                    f"Cache refreshed after {self.batch_create_count} new alerts."
                )
                self.batch_create_count = 0

            return alert
        except Exception as e:
            await session.rollback()
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

    async def get_active_rsi_alerts(self, session: AsyncSession) -> List[Alert]:
        """활성화된 RSI 알림 조건만 조회"""
        query = (
            select(Alert)
            .where(Alert.is_active == True)
            .where(Alert.type == "rsi")
            .join(Alert.user)
        )
        result = await session.execute(query)
        alerts = result.scalars().all()
        logger.debug(f"Found {len(alerts)} active RSI alerts in database")
        return alerts

    async def check_rsi_alerts(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """RSI 알림 체크"""
        try:
            logger.debug("RSI 알림 조건 체크 시작")
            logger.debug(f"현재 RSI 데이터: {market_data['rsi']}")

            # RSI 알림만 조회하도록 수정
            active_alerts = await self.get_active_rsi_alerts(session)
            logger.debug(f"활성화된 RSI 알림 개수: {len(active_alerts)}")

            for alert in active_alerts:
                # interval이 None이거나 유효하지 않은 경우 스킵
                if not alert.interval or alert.interval not in [
                    "15m",
                    "1h",
                    "4h",
                    "1d",
                ]:
                    logger.warning(
                        f"유효하지 않은 interval - ID: {alert.id}, "
                        f"Interval: {alert.interval}"
                    )
                    continue

                current_rsi = market_data["rsi"].get(alert.interval)
                if current_rsi is None:
                    logger.warning(f"RSI 데이터 없음 - 간격: {alert.interval}")
                    continue

                logger.debug(
                    f"알림 정보: ID={alert.id}, 간격={alert.interval}, "
                    f"설정값={alert.threshold}, 현재값={current_rsi}, 방향={alert.direction}"
                )

                if self._check_threshold_condition(
                    current_rsi, alert.threshold, alert.direction
                ):
                    logger.info(f"알림 조건 충족! ID: {alert.id}")
                    await self.trigger_alert(
                        session,
                        alert,
                        {
                            "type": "RSI",
                            "interval": alert.interval,
                            "value": current_rsi,
                            "threshold": alert.threshold,
                            "direction": alert.direction,
                        },
                    )
                else:
                    logger.debug(
                        f"알림 조건 미충족 - ID: {alert.id}, "
                        f"현재값: {current_rsi}, 설정값: {alert.threshold}, "
                        f"방향: {alert.direction}"
                    )

        except Exception as e:
            logger.error(f"RSI 알림 체크 중 오류 발생: {str(e)}")
            logger.exception(e)

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
                elif alert.type == "dominance":
                    self.alert_cache["dominance"].append(alert)
                    logger.debug(f"Added dominance alert: {alert.id}")
                elif alert.type == "mvrv":
                    self.alert_cache["mvrv"].append(alert)
                    logger.debug(f"Added MVRV alert: {alert.id}")

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

            # price 알림 체크
            await self.check_price_alerts(session, market_data)

            # 김치프리미엄 알림 체크
            if "kimchi_premium" in market_data:
                await self.check_kimchi_premium_alerts(session, market_data)

            # 도미넌스 알림 체크
            if "dominance" in market_data:
                await self.check_dominance_alerts(session, market_data)

            # MVRV 알림 체크
            if "mvrv" in market_data:
                await self.check_mvrv_alerts(session, market_data)

        except Exception as e:
            logger.error(f"Error in process_market_data: {str(e)}")
            logger.exception(e)

    async def check_kimchi_premium_alerts(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """김치프리미엄 알림 체크"""
        try:
            current_premium = market_data["kimchi_premium"]
            logger.debug(f"Checking premium alerts. Current premium: {current_premium}")

            for alert in self.alert_cache["kimchi_premium"]:
                if self._check_threshold_condition(
                    current_premium, alert.threshold, alert.direction
                ):
                    logger.info(
                        f"Premium alert triggered: {alert.id}, Premium: {current_premium}"
                    )
                    await self.trigger_alert(
                        session,
                        alert,
                        {
                            "type": "kimchi_premium",
                            "value": current_premium,
                            "threshold": alert.threshold,
                            "direction": alert.direction,
                        },
                    )
        except Exception as e:
            logger.error(f"Error checking kimchi premium alerts: {str(e)}")

    async def check_dominance_alerts(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """도미넌스 알림 체크"""
        try:
            current_dominance = market_data["dominance"]
            logger.debug(
                f"Checking dominance alerts. Current dominance: {current_dominance}"
            )

            for alert in self.alert_cache["dominance"]:
                if self._check_threshold_condition(
                    current_dominance, alert.threshold, alert.direction
                ):
                    logger.info(
                        f"Dominance alert triggered: {alert.id}, Dominance: {current_dominance}"
                    )
                    await self.trigger_alert(
                        session,
                        alert,
                        {
                            "type": "dominance",
                            "value": current_dominance,
                            "threshold": alert.threshold,
                            "direction": alert.direction,
                        },
                    )
        except Exception as e:
            logger.error(f"Error checking dominance alerts: {str(e)}")

    async def check_mvrv_alerts(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """MVRV 알림 체크"""
        try:
            current_mvrv = market_data["mvrv"]
            logger.debug(f"Checking MVRV alerts. Current MVRV: {current_mvrv}")

            for alert in self.alert_cache["mvrv"]:
                if self._check_threshold_condition(
                    current_mvrv, alert.threshold, alert.direction
                ):
                    logger.info(
                        f"MVRV alert triggered: {alert.id}, MVRV: {current_mvrv}"
                    )
                    await self.trigger_alert(
                        session,
                        alert,
                        {
                            "type": "mvrv",
                            "value": current_mvrv,
                            "threshold": alert.threshold,
                            "direction": alert.direction,
                        },
                    )
        except Exception as e:
            logger.error(f"Error checking MVRV alerts: {str(e)}")

    async def check_price_alerts(
        self, session: AsyncSession, market_data: Dict[str, Any]
    ):
        """Price 알림 체크 로직 분리"""
        for currency in ["KRW", "USD"]:
            new_price = market_data["krw"] if currency == "KRW" else market_data["usd"]
            old_price = self.last_price_by_currency[currency]

            # 첫 호출이라면 흐름 판단 불가 -> 초기값 저장 후 스킵
            if old_price is None:
                self.last_price_by_currency[currency] = new_price
                continue

            logger.debug(
                f"Checking price alerts for {currency}. "
                f"old_price={old_price}, new_price={new_price}"
            )

            # threshold별 알림 목록을 순회하며 돌파 여부를 체크
            for threshold, alert_list in self.alert_cache["price"].items():
                alerts = [
                    a for a in alert_list if a.currency == currency and a.is_active
                ]

                for alert in alerts:
                    crossing = False
                    if alert.direction == "above":
                        # 예: (old_price < threshold <= new_price)면 상향 돌파
                        crossing = old_price < threshold <= new_price
                    else:
                        # 예: (old_price > threshold >= new_price)면 하향 돌파
                        crossing = old_price > threshold >= new_price

                    if crossing:
                        logger.info(
                            f"Price alert triggered: {alert.id}, "
                            f"old_price={old_price}, new_price={new_price}, "
                            f"threshold={threshold}, direction={alert.direction}"
                        )
                        await self.trigger_alert(session, alert)

            # 마지막에 currency별 가격을 갱신
            self.last_price_by_currency[currency] = new_price

    def _check_threshold_condition(
        self, current_value: float, threshold: float, direction: str
    ) -> bool:
        """임계값 조건 체크 로직"""
        try:
            logger.debug(
                f"임계값 조건 체크: 현재값={current_value}, 기준값={threshold}, 방향={direction}"
            )
            if direction == "above":
                result = current_value > threshold
            else:  # "below"
                result = current_value < threshold
            logger.debug(f"조건 체크 결과: {result}")
            return result
        except Exception as e:
            logger.error(f"임계값 조건 체크 중 오류: {str(e)}")
            return False

    async def trigger_alert(
        self,
        session: AsyncSession,
        alert: Alert,
        additional_data: Dict[str, Any] = None,
    ):
        """알림 발생 시 처리"""
        async with self.trigger_lock:
            try:
                # 동시에 같은 alert를 트리거하지 않도록 락을 걸고 추가 검사
                check_stmt = (
                    select(Alert)
                    .where(Alert.id == alert.id)
                    .where(Alert.is_active == True)
                )
                result = await session.execute(check_stmt)
                if not result.scalar_one_or_none():
                    logger.debug(
                        f"Alert {alert.id} is already inactive or does not exist, skipping."
                    )
                    return

                stmt = (
                    select(Alert)
                    .options(joinedload(Alert.user))
                    .where(Alert.id == alert.id)
                )
                select_result = await session.execute(stmt)
                alert_with_user = select_result.unique().scalar_one()

                # 알림 비활성화
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

                # 캐시 갱신
                self.last_cache_update = None
                await self.refresh_cache(session)

                # 푸시 알림 전송
                message = self.create_alert_message(alert_with_user, additional_data)
                if alert_with_user.user and alert_with_user.user.fcm_token:
                    logger.info(
                        f"Attempting to send notification to token: {alert_with_user.user.fcm_token[:10]}..."
                    )
                    response = await push_service.send_push_notification(
                        token=alert_with_user.user.fcm_token,
                        title="BitNow 알림",
                        body=message,
                    )

                    # FCM 응답 처리 추가
                    if not response:
                        logger.error("FCM notification failed to send")
                        # 토큰이 유효하지 않은 경우
                        if "InvalidRegistration" in str(
                            response
                        ) or "NotRegistered" in str(response):
                            logger.info(
                                f"Removing invalid FCM token for user {alert_with_user.user.id}"
                            )
                            # 사용자의 FCM 토큰 제거
                            alert_with_user.user.fcm_token = None
                            await session.commit()
                    else:
                        logger.info(f"FCM notification sent successfully: {message}")
                else:
                    logger.warning(
                        f"User has no FCM token for alert ID: {alert_with_user.id}"
                    )
            except Exception as e:
                logger.error(f"Failed to trigger alert: {str(e)}")
                logger.exception(e)

    def create_alert_message(
        self, alert: Alert, additional_data: Dict[str, Any] = None
    ) -> str:
        """알림 메시지 생성"""
        if alert.type == "rsi" and additional_data:
            direction_text = (
                "상향 돌파!" if alert.direction == "above" else "하향 돌파!"
            )
            message = (
                f"{alert.symbol} {alert.interval} RSI "
                f"{alert.threshold} {direction_text}"
            )
        elif alert.type == "price":
            direction_text = (
                "상향 돌파!" if alert.direction == "above" else "하향 돌파!"
            )
            currency = alert.currency or "KRW"
            price = (
                f"{alert.threshold:,.0f}"
                if currency == "KRW"
                else f"${alert.threshold:,.0f}"
            )
            message = f"{alert.symbol} {price} {direction_text}"
        elif alert.type == "kimchi_premium":
            direction_text = "이상!" if alert.direction == "above" else "이하!"
            message = f"{alert.symbol} 김치프리미엄 {alert.threshold}% {direction_text}"
        elif alert.type == "dominance":
            direction_text = "이상!" if alert.direction == "above" else "이하!"
            message = f"{alert.symbol} 도미넌스 {alert.threshold}% {direction_text}"
        elif alert.type == "mvrv":
            direction_text = "이상!" if alert.direction == "above" else "이하!"
            message = f"{alert.symbol} MVRV {alert.threshold} {direction_text}"
        else:
            direction_text = (
                "상향 돌파!" if alert.direction == "above" else "하향 돌파!"
            )
            message = f"{alert.symbol} {alert.type} {alert.threshold} {direction_text}"

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
