import json
import asyncio
import websockets
from typing import Set, Dict, Any
from datetime import datetime
import logging
from app.constants import (
    UPBIT_WS_URL,
    BINANCE_WS_URL,
    DEFAULT_PING_INTERVAL,
    MAX_RECONNECT_ATTEMPTS,
    RECONNECT_DELAY,
)
import aiohttp
from app.services.exchange_service import exchange_service  # 환율 서비스 import
from app.services.indicator_service import indicator_service  # RSI 서비스 import
from app.services.alert_service import alert_service
from app.database import async_session  # 추가
from app.services.price_service import check_ma_cross_all  # 상단에 추가

# SQLAlchemy 로거 비활성화 추가
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PriceStreamService:
    def __init__(self):
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.current_prices: Dict[str, Any] = {
            "krw": 0.0,
            "usd": 0.0,
            "timestamp": "",
            "kimchi_premium": 0.0,
            "change_24h": {"krw": 0.0, "usd": 0.0},
            "volume": {  # 시간 간격별 누적 거래량 정보
                "1m": {"krw": 0.0, "usd": 0.0},
                "5m": {"krw": 0.0, "usd": 0.0},
                "15m": {"krw": 0.0, "usd": 0.0},
                "1h": {"krw": 0.0, "usd": 0.0},
                "24h": {"krw": 0.0, "usd": 0.0},
            },
            "rsi": {
                "15m": 0.0,
                "1h": 0.0,
                "4h": 0.0,
                "1d": 0.0,
            },
            "dominance": 0.0,
            "high_3w": {
                "krw": 0.0,
                "usd": 0.0,
                "timestamp": "",
            },
            "ma_cross": None,  # MA 크로스 데이터 캐시 추가
            "fear_greed": {  # 공포/탐욕 지수 추가
                "value": 0,
                "classification": "neutral",
                "timestamp": "",
            },
        }
        self.prev_prices: Dict[str, Any] = {"krw": 0.0, "usd": 0.0, "timestamp": ""}
        # 시간 간격별 마지막 갱신 시간
        self.last_volume_update = {
            "1m": datetime.now(),
            "5m": datetime.now(),
            "15m": datetime.now(),
            "1h": datetime.now(),
            "24h": datetime.now(),
        }
        # 캔들 데이터 캐시
        self.candle_cache = {"krw": {}, "usd": {}}
        self.running = False
        self.last_broadcast_time = datetime.now()
        self.broadcast_interval = 1.0  # 1초로 변경
        self.db_session = None  # 추가

    async def calculate_kimchi_premium(
        self, krw_price: float, usd_price: float
    ) -> float:
        """김치 프리미엄 계산"""
        try:
            exchange_rate = await exchange_service.get_usd_krw_rate()
            premium = ((krw_price / (usd_price * exchange_rate)) - 1) * 100
            return round(premium, 2)
        except Exception as e:
            logger.error(f"Failed to calculate kimchi premium: {str(e)}")
            return 0.0

    async def should_broadcast(self) -> bool:
        """브로드캐스트 주기 제한 확인"""
        now = datetime.now()
        if (now - self.last_broadcast_time).total_seconds() >= self.broadcast_interval:
            self.last_broadcast_time = now
            return True
        return False

    async def connect_upbit(self):
        """업비트 WebSocket 연결 및 데이터 처리"""
        logger.info("Connecting to Upbit WebSocket...")
        while self.running:
            try:
                async with websockets.connect(UPBIT_WS_URL) as websocket:
                    logger.info("Successfully connected to Upbit WebSocket")
                    await self.fetch_upbit_24h_change()

                    subscribe_fmt = [
                        {"ticket": "UNIQUE_TICKET"},
                        {"type": "trade", "codes": ["KRW-BTC"], "isOnlyRealtime": True},
                    ]
                    await websocket.send(json.dumps(subscribe_fmt))
                    logger.info("Sent subscription message to Upbit")

                    while self.running:
                        data = await websocket.recv()
                        data = json.loads(data)
                        self.current_prices["krw"] = float(data["trade_price"])
                        self.current_prices["timestamp"] = datetime.now().isoformat()

                        # 브로드캐스트 주기와 관계없이 항상 알림 체크
                        if self.current_prices["usd"] > 0:
                            self.current_prices["kimchi_premium"] = (
                                await self.calculate_kimchi_premium(
                                    self.current_prices["krw"],
                                    self.current_prices["usd"],
                                )
                            )

                        # 알림 체크는 항상 실행
                        await self.broadcast(self.current_prices)

            except Exception as e:
                logger.error(f"Upbit WebSocket error: {str(e)}")
                await asyncio.sleep(RECONNECT_DELAY)

    async def fetch_upbit_24h_change(self):
        """업비트 24시간 변동률 조회"""
        try:
            url = "https://api.upbit.com/v1/ticker"
            params = {"markets": "KRW-BTC"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        change_rate = float(data[0]["change_rate"]) * 100
                        self.current_prices["change_24h"]["krw"] = round(change_rate, 2)
        except Exception as e:
            logger.error(f"Failed to fetch Upbit 24h change: {str(e)}")

    async def fetch_binance_24h_change(self):
        """바이낸스 24시간 변동률 조회"""
        try:
            url = "https://api.binance.com/api/v3/ticker/24hr"
            params = {"symbol": "BTCUSDT"}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        change_rate = float(data["priceChangePercent"])
                        self.current_prices["change_24h"]["usd"] = round(change_rate, 2)
        except Exception as e:
            logger.error(f"Failed to fetch Binance 24h change: {str(e)}")

    async def connect_binance(self):
        """바이낸스 WebSocket 연결 및 데이터 처리"""
        logger.info("Connecting to Binance WebSocket...")
        while self.running:
            try:
                async with websockets.connect(BINANCE_WS_URL) as websocket:
                    logger.info("Successfully connected to Binance WebSocket")
                    await self.fetch_binance_24h_change()

                    while self.running:
                        data = await websocket.recv()
                        data = json.loads(data)
                        self.current_prices["usd"] = float(data["p"])
                        self.current_prices["timestamp"] = datetime.now().isoformat()

                        # 브로드캐스트 주기와 관계없이 항상 알림 체크
                        if self.current_prices["krw"] > 0:
                            self.current_prices["kimchi_premium"] = (
                                await self.calculate_kimchi_premium(
                                    self.current_prices["krw"],
                                    self.current_prices["usd"],
                                )
                            )

                        # 알림 체크는 항상 실행
                        await self.broadcast(self.current_prices)

            except Exception as e:
                logger.error(f"Binance WebSocket error: {str(e)}")
                await asyncio.sleep(RECONNECT_DELAY)

    async def broadcast(self, message: Dict[str, Any]):
        """연결된 모든 클라이언트에게 메시지 전송 및 알림 체크"""
        # 알림 체크는 클라이언트 연결 여부와 관계없이 항상 실행
        try:
            async with async_session() as session:
                await alert_service.process_market_data(session, message)
        except Exception as e:
            logger.error(f"Error checking alerts: {str(e)}")
            logger.exception(e)

        # 클라이언트가 있을 때만 메시지 전송 (1초 주기 제한)
        if self.clients:
            now = datetime.now()
            if (
                now - self.last_broadcast_time
            ).total_seconds() >= self.broadcast_interval:
                disconnected_clients = set()
                message_str = json.dumps(message)
                for client in self.clients:
                    try:
                        await client.send_text(message_str)
                    except Exception as e:
                        logger.error(f"Failed to send message to client: {str(e)}")
                        disconnected_clients.add(client)
                self.clients -= disconnected_clients
                self.last_broadcast_time = now

    async def add_client(self, websocket: websockets.WebSocketServerProtocol):
        """새로운 클라이언트 연결 추가"""
        self.clients.add(websocket)
        logger.info(f"New client connected. Total clients: {len(self.clients)}")

        # 현재 가격 즉시 전송
        try:
            await websocket.send_text(json.dumps(self.current_prices))
        except Exception as e:
            logger.error(f"Failed to send initial prices to client: {str(e)}")

    async def remove_client(self, websocket: websockets.WebSocketServerProtocol):
        """클라이언트 연결 제거"""
        self.clients.remove(websocket)
        logger.info(f"Client disconnected. Total clients: {len(self.clients)}")

    async def update_rsi(self, interval: str):
        """특정 간격의 RSI 업데이트"""
        try:
            rsi_data = await indicator_service.calculate_rsi("BTC", interval, 14)
            self.current_prices["rsi"][interval] = round(float(rsi_data["rsi"]), 2)
            logger.debug(
                f"Updated RSI for interval {interval}: {self.current_prices['rsi'][interval]}"
            )

            # RSI 업데이트 시마다 알림 체크
            async with async_session() as session:
                await alert_service.check_rsi_alerts(session, self.current_prices)

        except Exception as e:
            logger.error(f"Failed to update RSI for interval {interval}: {str(e)}")

    async def update_all_rsi(self):
        """모든 간격의 RSI 초기 업데이트"""
        for interval in ["15m", "1h", "4h", "1d"]:
            await self.update_rsi(interval)

    async def start_rsi_updates(self):
        """RSI 주기적 업데이트"""
        while self.running:
            try:
                # 모든 간격의 RSI를 1분마다 업데이트
                for interval in ["15m", "1h", "4h", "1d"]:
                    await self.update_rsi(interval)
                await asyncio.sleep(60)  # 1분 대기
            except Exception as e:
                logger.error(f"RSI 업데이트 중 오류 발생: {str(e)}")
                await asyncio.sleep(10)  # 오류 발생시 10초 대기

    async def update_dominance(self):
        """도미넌스 업데이트"""
        try:
            dominance_data = await indicator_service.get_btc_dominance()
            self.current_prices["dominance"] = dominance_data["dominance"]
            logger.info(f"Updated Dominance: {self.current_prices['dominance']}")
        except Exception as e:
            logger.error(f"Failed to update Dominance: {str(e)}")

    async def start_dominance_updates(self):
        """도미넌스 주기적 업데이트 (60분마다)"""
        while self.running:
            try:
                await self.update_dominance()
                await asyncio.sleep(60 * 60)  # 60분 대기
            except Exception as e:
                logger.error(f"Error in Dominance update: {str(e)}")
                await asyncio.sleep(60)

    async def update_mvrv(self):
        """MVRV 업데이트"""
        try:
            # db 세션 생성
            async with async_session() as session:
                mvrv_data = await indicator_service.get_mvrv(session)
                self.current_prices["mvrv"] = mvrv_data["mvrv"]
                logger.info(f"Updated MVRV: {self.current_prices['mvrv']}")
        except Exception as e:
            logger.error(f"Failed to update MVRV: {str(e)}")

    async def start_mvrv_updates(self):
        """MVRV 주기적 업데이트 (60분마다)"""
        while self.running:
            try:
                await self.update_mvrv()
                await asyncio.sleep(60 * 60)  # 60분 대기
            except Exception as e:
                logger.error(f"Error in MVRV update: {str(e)}")
                await asyncio.sleep(60)

    async def update_3w_high(self):
        """3주 최고가 업데이트"""
        try:
            # 바이낸스와 업비트에서 3주치 일봉 데이터 조회
            candles_upbit = await exchange_service.get_upbit_candles(
                "KRW-BTC", "1d", 21
            )  # 3주 = 21일
            candles_binance = await exchange_service.get_binance_candles(
                "BTCUSDT", "1d", 21
            )

            if candles_upbit and candles_binance:
                # KRW 최고가 계산
                krw_high = max(float(candle["high"]) for candle in candles_upbit)
                krw_high_candle = max(candles_upbit, key=lambda x: float(x["high"]))

                # USD 최고가 계산
                usd_high = max(float(candle["high"]) for candle in candles_binance)
                usd_high_candle = max(candles_binance, key=lambda x: float(x["high"]))

                self.current_prices["high_3w"] = {
                    "krw": krw_high,
                    "usd": usd_high,
                    "krw_timestamp": krw_high_candle["timestamp"],
                    "usd_timestamp": usd_high_candle["timestamp"],
                }

                logger.info(
                    f"3주 최고가 업데이트 - KRW: {krw_high:,.0f}, USD: {usd_high:,.2f}"
                )

        except Exception as e:
            logger.error(f"3주 최고가 업데이트 중 오류 발생: {str(e)}")

    async def start_3w_high_updates(self):
        """3주 최고가 주기적 업데이트 (24시간마다)"""
        while self.running:
            try:
                await self.update_3w_high()
                await asyncio.sleep(24 * 60 * 60)  # 24시간 대기
            except Exception as e:
                logger.error(f"3주 최고가 업데이트 태스크 오류: {str(e)}")
                await asyncio.sleep(60)  # 오류 발생시 1분 후 재시도

    async def update_ma_cross(self):
        """이동평균선 돌파 여부 업데이트"""
        try:
            ma_data = await check_ma_cross_all()
            if "error" not in ma_data:
                # 캐시에 MA 크로스 데이터 저장
                self.current_prices["ma_cross"] = ma_data
                logger.info("MA cross data cached successfully")

                # DB 세션 생성 및 알림 체크만 수행
                async with async_session() as session:
                    await alert_service.check_ma_alerts(session, ma_data)
        except Exception as e:
            logger.error(f"Failed to update MA cross data: {str(e)}")

    async def start_ma_cross_updates(self):
        """이동평균선 돌파 체크 주기적 업데이트 (24시간마다)"""
        while self.running:
            try:
                await self.update_ma_cross()
                await asyncio.sleep(24 * 60 * 60)  # 24시간 대기
            except Exception as e:
                logger.error(f"Error in MA cross update: {str(e)}")
                await asyncio.sleep(60)  # 오류 발생시 1분 후 재시도

    async def reset_manual_exchange_rate(self):
        """수동 설정된 환율 초기화 (24시간마다)"""
        while self.running:
            try:
                await exchange_service.reset_manual_rate()
                logger.info("Manual exchange rate has been reset")
                await asyncio.sleep(24 * 60 * 60)  # 24시간 대기
            except Exception as e:
                logger.error(f"Error in exchange rate reset: {str(e)}")
                await asyncio.sleep(60)  # 오류 발생시 1분 후 재시도

    async def update_fear_greed(self):
        """공포/탐욕 지수 업데이트"""
        try:
            # db 세션 생성
            async with async_session() as session:
                fear_greed_data = await indicator_service.get_fear_greed_index(session)
                self.current_prices["fear_greed"] = {
                    "value": fear_greed_data["value"],
                    "classification": fear_greed_data["classification"],
                    "timestamp": fear_greed_data["timestamp"],
                }
                logger.info(
                    f"공포/탐욕 지수 업데이트: {self.current_prices['fear_greed']['value']} ({self.current_prices['fear_greed']['classification']})"
                )

                # 알림 체크 부분 제거 (필요 없음)
                # await alert_service.check_fear_greed_alerts(
                #     session, self.current_prices
                # )
        except Exception as e:
            logger.error(f"공포/탐욕 지수 업데이트 중 오류 발생: {str(e)}")

    async def start_fear_greed_updates(self):
        """공포/탐욕 지수 주기적 업데이트 (24시간마다)"""
        while self.running:
            try:
                await self.update_fear_greed()
                await asyncio.sleep(24 * 60 * 60)  # 24시간 대기
            except Exception as e:
                logger.error(f"공포/탐욕 지수 업데이트 태스크 오류: {str(e)}")
                await asyncio.sleep(60)  # 오류 발생시 1분 후 재시도

    async def start(self):
        """스트리밍 서비스 시작"""
        try:
            self.running = True
            logger.info("WebSocket 스트리밍 서비스 시작 중...")

            # 초기값 설정
            await self.update_all_rsi()
            await self.update_dominance()
            await self.update_mvrv()
            await self.update_3w_high()
            await self.update_ma_cross()  # MA 크로스 초기값 설정
            await self.update_fear_greed()  # 공포/탐욕 지수 초기값 설정

            # 기존 태스크들 시작
            asyncio.create_task(self.start_rsi_updates())
            asyncio.create_task(self.start_dominance_updates())
            asyncio.create_task(self.start_mvrv_updates())
            asyncio.create_task(self.update_24h_changes())
            asyncio.create_task(self.start_3w_high_updates())
            asyncio.create_task(
                self.start_ma_cross_updates()
            )  # MA 크로스 업데이트 태스크 추가
            asyncio.create_task(
                self.reset_manual_exchange_rate()
            )  # 환율 초기화 태스크 추가
            asyncio.create_task(
                self.start_fear_greed_updates()
            )  # 공포/탐욕 지수 업데이트 태스크 추가
            asyncio.create_task(self.connect_upbit())
            asyncio.create_task(self.connect_binance())

            logger.info("WebSocket 스트리밍 서비스가 성공적으로 시작되었습니다")
        except Exception as e:
            logger.error(f"스트리밍 서비스 시작 실패: {str(e)}")
            self.running = False

    async def update_24h_changes(self):
        """24시간 변동률 주기적 업데이트 (1분마다)"""
        while self.running:
            await self.fetch_upbit_24h_change()
            await self.fetch_binance_24h_change()
            await self.update_volume_data()
            await asyncio.sleep(60)  # 1분 대기

    async def fetch_upbit_candles(self, interval: str) -> Dict[str, float]:
        """업비트 API에서 특정 간격의 캔들 데이터 가져오기"""
        try:
            # 업비트 간격 형식 변환 (1m, 5m, 15m, 60m, 24h)
            upbit_interval = {
                "1m": "minutes/1",
                "5m": "minutes/5",
                "15m": "minutes/15",
                "1h": "minutes/60",
                "24h": "days",
            }.get(interval, "minutes/1")

            url = f"https://api.upbit.com/v1/candles/{upbit_interval}"
            params = {"market": "KRW-BTC", "count": 1}  # 가장 최근 캔들 1개만 가져오기

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            candle = data[0]
                            # 거래량 및 시간 추출
                            volume = float(candle.get("candle_acc_trade_volume", 0))
                            timestamp = candle.get("candle_date_time_utc", "")

                            # 캐시 저장
                            self.candle_cache["krw"][interval] = {
                                "volume": volume,
                                "timestamp": timestamp,
                            }

                            return {"volume": volume, "timestamp": timestamp}

            # 요청 실패 시 캐시된 데이터 사용
            if interval in self.candle_cache["krw"]:
                return self.candle_cache["krw"][interval]

            return {"volume": 0.0, "timestamp": ""}
        except Exception as e:
            logger.error(f"업비트 캔들 데이터 가져오기 오류: {str(e)}")
            # 오류 발생 시 캐시된 데이터 사용
            if interval in self.candle_cache["krw"]:
                return self.candle_cache["krw"][interval]
            return {"volume": 0.0, "timestamp": ""}

    async def fetch_binance_candles(self, interval: str) -> Dict[str, float]:
        """바이낸스 API에서 특정 간격의 캔들 데이터 가져오기"""
        try:
            # 바이낸스 간격 형식 변환 (1m, 5m, 15m, 1h, 1d)
            binance_interval = {
                "1m": "1m",
                "5m": "5m",
                "15m": "15m",
                "1h": "1h",
                "24h": "1d",
            }.get(interval, "1m")

            url = "https://api.binance.com/api/v3/klines"
            params = {
                "symbol": "BTCUSDT",
                "interval": binance_interval,
                "limit": 1,  # 가장 최근 캔들 1개만 가져오기
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            # 바이낸스 응답 형식: [
                            # [개장시간, 개장가, 최고가, 최저가, 종가, 거래량, ...]]
                            candle = data[0]
                            volume = float(candle[5])  # 5번째 인덱스가 거래량
                            timestamp = datetime.fromtimestamp(
                                candle[0] / 1000
                            ).isoformat()

                            # 캐시 저장
                            self.candle_cache["usd"][interval] = {
                                "volume": volume,
                                "timestamp": timestamp,
                            }

                            return {"volume": volume, "timestamp": timestamp}

            # 요청 실패 시 캐시된 데이터 사용
            if interval in self.candle_cache["usd"]:
                return self.candle_cache["usd"][interval]

            return {"volume": 0.0, "timestamp": ""}
        except Exception as e:
            logger.error(f"바이낸스 캔들 데이터 가져오기 오류: {str(e)}")
            # 오류 발생 시 캐시된 데이터 사용
            if interval in self.candle_cache["usd"]:
                return self.candle_cache["usd"][interval]
            return {"volume": 0.0, "timestamp": ""}

    async def update_volume_data(self):
        """REST API를 사용하여 모든 시간 간격의 거래량 업데이트"""
        # 시간 간격 정의
        intervals = ["1m", "5m", "15m", "1h", "24h"]

        for interval in intervals:
            # 업데이트 주기 체크
            minutes_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "24h": 24 * 60}
            minutes = minutes_map[interval]
            update_interval = max(
                1, minutes // 5
            )  # 최소 1분마다, 간격의 1/5 주기로 업데이트

            current_time = datetime.now()
            time_diff = (
                current_time - self.last_volume_update[interval]
            ).total_seconds() / 60

            if time_diff >= update_interval:
                # 업비트(KRW) 거래량 가져오기
                upbit_data = await self.fetch_upbit_candles(interval)
                self.current_prices["volume"][interval]["krw"] = upbit_data["volume"]

                # 바이낸스(USD) 거래량 가져오기
                binance_data = await self.fetch_binance_candles(interval)
                self.current_prices["volume"][interval]["usd"] = binance_data["volume"]

                # 마지막 업데이트 시간 기록
                self.last_volume_update[interval] = current_time

        logger.info(f"거래량 데이터 업데이트 완료: {current_time.isoformat()}")

    async def stop(self):
        """스트리밍 서비스 중지"""
        self.running = False
        for client in self.clients:
            await client.close()
        self.clients.clear()


# 싱글톤 인스턴스 생성
stream_service = PriceStreamService()
