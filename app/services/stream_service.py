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
            "rsi": {
                "15m": 0.0,
                "1h": 0.0,
                "4h": 0.0,
                "1d": 0.0,
            },
            "mvrv": 0.0,
            "dominance": 0.0,
        }
        self.prev_prices: Dict[str, float] = {"krw": 0.0, "usd": 0.0, "timestamp": ""}
        self.running = False
        self.last_broadcast_time = datetime.now()
        self.broadcast_interval = 1.0  # 1초로 변경

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

                        # 브로드캐스트 주기 제한
                        if await self.should_broadcast():
                            # 브로드캐스트 시점에 김치프리미엄 계산
                            if self.current_prices["usd"] > 0:
                                self.current_prices["kimchi_premium"] = (
                                    await self.calculate_kimchi_premium(
                                        self.current_prices["krw"],
                                        self.current_prices["usd"],
                                    )
                                )
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

                        # 브로드캐스트 주기 제한
                        if await self.should_broadcast():
                            # 브로드캐스트 시점에 김치프리미엄 계산
                            if self.current_prices["krw"] > 0:
                                self.current_prices["kimchi_premium"] = (
                                    await self.calculate_kimchi_premium(
                                        self.current_prices["krw"],
                                        self.current_prices["usd"],
                                    )
                                )
                            await self.broadcast(self.current_prices)

            except Exception as e:
                logger.error(f"Binance WebSocket error: {str(e)}")
                await asyncio.sleep(RECONNECT_DELAY)

    async def broadcast(self, message: Dict[str, Any]):
        """연결된 모든 클라이언트에게 메시지 전송"""
        if self.clients:
            disconnected_clients = set()
            message_str = json.dumps(message)

            for client in self.clients:
                try:
                    await client.send_text(message_str)
                except Exception as e:
                    logger.error(f"Failed to send message to client: {str(e)}")
                    disconnected_clients.add(client)

            # 연결 끊긴 클라이언트 제거
            self.clients -= disconnected_clients

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
            logger.info(
                f"Updated RSI for interval {interval}: {self.current_prices['rsi'][interval]}"
            )
        except Exception as e:
            logger.error(f"Failed to update RSI for interval {interval}: {str(e)}")

    async def update_all_rsi(self):
        """모든 간격의 RSI 초기 업데이트"""
        for interval in ["15m", "1h", "4h", "1d"]:
            await self.update_rsi(interval)

    async def start_rsi_updates(self):
        """RSI 주기적 업데이트 시작"""
        while self.running:
            try:
                # 15분 RSI 업데이트
                await self.update_rsi("15m")
                await asyncio.sleep(15 * 60)  # 15분 대기
            except Exception as e:
                logger.error(f"Error in 15m RSI update: {str(e)}")
                await asyncio.sleep(60)

    async def start_hourly_rsi_updates(self):
        """1시간 RSI 업데이트"""
        while self.running:
            try:
                await self.update_rsi("1h")
                await asyncio.sleep(60 * 60)  # 1시간 대기
            except Exception as e:
                logger.error(f"Error in 1h RSI update: {str(e)}")
                await asyncio.sleep(60)

    async def start_4h_rsi_updates(self):
        """4시간 RSI 업데이트"""
        while self.running:
            try:
                await self.update_rsi("4h")
                await asyncio.sleep(4 * 60 * 60)  # 4시간 대기
            except Exception as e:
                logger.error(f"Error in 4h RSI update: {str(e)}")
                await asyncio.sleep(60)

    async def start_daily_rsi_updates(self):
        """일간 RSI 업데이트"""
        while self.running:
            try:
                await self.update_rsi("1d")
                await asyncio.sleep(24 * 60 * 60)  # 24시간 대기
            except Exception as e:
                logger.error(f"Error in daily RSI update: {str(e)}")
                await asyncio.sleep(60)

    async def update_mvrv(self):
        """MVRV 업데이트"""
        try:
            mvrv_data = await indicator_service.get_mvrv()
            self.current_prices["mvrv"] = mvrv_data["mvrv"]
            logger.info(f"Updated MVRV: {self.current_prices['mvrv']}")
        except Exception as e:
            logger.error(f"Failed to update MVRV: {str(e)}")

    async def start_mvrv_updates(self):
        """MVRV 주기적 업데이트 (1시간마다)"""
        while self.running:
            try:
                await self.update_mvrv()
                await asyncio.sleep(60 * 60)  # 1시간 대기
            except Exception as e:
                logger.error(f"Error in MVRV update: {str(e)}")
                await asyncio.sleep(60)

    async def update_dominance(self):
        """도미넌스 업데이트"""
        try:
            dominance_data = await indicator_service.get_btc_dominance()
            self.current_prices["dominance"] = dominance_data["dominance"]
            logger.info(f"Updated Dominance: {self.current_prices['dominance']}")
        except Exception as e:
            logger.error(f"Failed to update Dominance: {str(e)}")

    async def start_dominance_updates(self):
        """도미넌스 주기적 업데이트 (1시간마다)"""
        while self.running:
            try:
                await self.update_dominance()
                await asyncio.sleep(60 * 60)  # 1시간 대기
            except Exception as e:
                logger.error(f"Error in Dominance update: {str(e)}")
                await asyncio.sleep(60)

    async def start(self):
        """스트리밍 서비스 시작"""
        try:
            self.running = True
            logger.info("Starting WebSocket streaming service...")

            # 초기값 설정
            await self.update_all_rsi()
            await self.update_mvrv()
            await self.update_dominance()

            # 업데이트 태스크 시작
            asyncio.create_task(self.start_rsi_updates())
            asyncio.create_task(self.start_hourly_rsi_updates())
            asyncio.create_task(self.start_4h_rsi_updates())
            asyncio.create_task(self.start_daily_rsi_updates())
            asyncio.create_task(self.start_mvrv_updates())
            asyncio.create_task(self.start_dominance_updates())

            # 기존 태스크들
            asyncio.create_task(self.update_24h_changes())
            asyncio.create_task(self.connect_upbit())
            asyncio.create_task(self.connect_binance())

            logger.info("WebSocket streaming service started successfully")
        except Exception as e:
            logger.error(f"Failed to start streaming service: {str(e)}")
            self.running = False

    async def update_24h_changes(self):
        """24시간 변동률 주기적 업데이트 (1분마다)"""
        while self.running:
            await self.fetch_upbit_24h_change()
            await self.fetch_binance_24h_change()
            await asyncio.sleep(60)  # 1분 대기

    async def stop(self):
        """스트리밍 서비스 중지"""
        self.running = False
        for client in self.clients:
            await client.close()
        self.clients.clear()


# 싱글톤 인스턴스 생성
stream_service = PriceStreamService()
