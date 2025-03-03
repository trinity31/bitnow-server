import aiohttp
from typing import Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.constants import (
    DEFAULT_USD_KRW_RATE,
    CACHE_DURATION_HOURS,
    EXCHANGE_RATE_API_URL,
    ALPHA_VANTAGE_URL,
)
import pandas as pd
from typing import List, Dict, Any
import logging

# .env 파일에서 환경변수 로드
load_dotenv()

logger = logging.getLogger(__name__)


class ExchangeRateService:
    def __init__(self):
        self.primary_url = EXCHANGE_RATE_API_URL
        self.backup_url = ALPHA_VANTAGE_URL
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.cached_rate = DEFAULT_USD_KRW_RATE
        self.last_update = None
        self.manual_rate = None  # 관리자가 수동 설정한 환율
        self.manual_rate_time = None

    def _is_cache_valid(self) -> bool:
        """캐시가 유효한지 확인합니다."""
        return (
            self.cached_rate is not None
            and self.last_update is not None
            and datetime.now() - self.last_update
            < timedelta(hours=CACHE_DURATION_HOURS)
        )

    def _update_cache(self, rate: float) -> None:
        """환율 캐시를 업데이트합니다."""
        self.cached_rate = rate
        self.last_update = datetime.now()
        print(f"조회된 환율: {rate}")

    async def _fetch_from_er_api(self) -> Optional[float]:
        """ExchangeRate-API에서 환율 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.primary_url) as response:
                    print("ExchangeRate-API Response status:", response.status)
                    if response.status == 200:
                        data = await response.json()
                        return data["rates"]["KRW"]
        except Exception as e:
            print(f"ExchangeRate-API 조회 실패: {str(e)}")
            return None

    async def _fetch_from_alpha_vantage(self) -> Optional[float]:
        """Alpha Vantage에서 환율 조회"""
        params = {
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": "USD",
            "to_currency": "KRW",
            "apikey": self.api_key,
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.backup_url, params=params) as response:
                    print("Alpha Vantage Response status:", response.status)
                    if response.status == 200:
                        data = await response.json()
                        return float(
                            data["Realtime Currency Exchange Rate"]["5. Exchange Rate"]
                        )
        except Exception as e:
            print(f"Alpha Vantage 조회 실패: {str(e)}")
            return None

    async def get_usd_krw_rate(self) -> float:
        """USD/KRW 환율 조회 (캐시 사용)"""
        # 수동 설정된 환율이 있으면 우선 사용
        if self.manual_rate is not None:
            # logger.debug(f"수동 설정된 환율 사용: {self.manual_rate}")
            return self.manual_rate

        # 캐시가 유효한지 확인
        now = datetime.now()
        if self.last_update and (now - self.last_update) < timedelta(
            hours=CACHE_DURATION_HOURS
        ):
            logger.debug(f"캐시된 환율 사용: {self.cached_rate}")
            return self.cached_rate

        try:
            # 첫 번째 API 시도
            rate = await self._fetch_from_alpha_vantage()

            # 실패하면 백업 API 시도
            if rate is None:
                rate = await self._fetch_from_er_api()

            # 성공적으로 가져왔다면 캐시 업데이트
            if rate is not None:
                self.cached_rate = rate
                self.last_update = now
                logger.info(f"새로운 환율 업데이트: {rate}")
                return rate

        except Exception as e:
            logger.error(f"Failed to fetch exchange rate: {str(e)}")

        # API 호출 실패시 캐시된 값 반환
        logger.warning(f"API 호출 실패, 캐시된 환율 사용: {self.cached_rate}")
        return self.cached_rate

    async def set_manual_rate(self, rate: float) -> dict:
        """관리자용 수동 환율 설정"""
        self.manual_rate = rate
        self.manual_rate_time = datetime.now()
        return {
            "rate": rate,
            "timestamp": self.manual_rate_time.isoformat(),
            "message": "환율이 수동으로 설정되었습니다",
        }

    async def reset_manual_rate(self) -> dict:
        """수동 설정 환율 초기화"""
        self.manual_rate = None
        self.manual_rate_time = None
        # 캐시도 초기화하여 새로운 환율을 즉시 가져오도록 함
        self.last_update = None

        # 새로운 환율 즉시 조회
        new_rate = await self.get_usd_krw_rate()

        return {
            "message": "수동 설정된 환율이 초기화되었습니다",
            "current_rate": new_rate,
        }

    async def get_candles(
        self, symbol: str = "BTC", interval: str = "15m", length: int = 14
    ) -> List[Dict[str, Any]]:
        """Binance에서 캔들 데이터를 가져오는 함수"""
        try:
            # Binance interval 포맷으로 변환
            interval_map = {
                "15m": "15m",
                "1h": "1h",
                "4h": "4h",
                "1d": "1d",
                "minute15": "15m",  # 이전 포맷 지원
                "minute60": "1h",  # 이전 포맷 지원
                "minute240": "4h",  # 이전 포맷 지원
                "day": "1d",  # 이전 포맷 지원
            }
            binance_interval = interval_map.get(interval)
            if not binance_interval:
                raise ValueError(f"Unsupported interval: {interval}")

            # Binance API 엔드포인트
            url = "https://api.binance.com/api/v3/klines"
            market = f"{symbol}USDT"
            params = {"symbol": market, "interval": binance_interval, "limit": length}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        candles = await response.json()
                        # Binance 캔들 데이터 포맷 변환
                        # [OpenTime, Open, High, Low, Close, Volume, ...]
                        return [
                            {
                                "timestamp": datetime.fromtimestamp(
                                    candle[0] / 1000
                                ).isoformat(),
                                "open": float(candle[1]),
                                "high": float(candle[2]),
                                "low": float(candle[3]),
                                "close": float(candle[4]),
                                "volume": float(candle[5]),
                            }
                            for candle in candles
                        ]
                    else:
                        raise Exception(f"Failed to fetch candles: {response.status}")
        except Exception as e:
            print(f"Error fetching candles: {str(e)}")
            raise e

    async def get_binance_candles(
        self, symbol: str = "BTCUSDT", interval: str = "1d", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """바이낸스 캔들 데이터 조회"""
        try:
            url = "https://api.binance.com/api/v3/klines"
            params = {"symbol": symbol, "interval": interval, "limit": limit}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 바이낸스 캔들 데이터 포맷 변환
                        candles = []
                        for item in data:
                            candle = {
                                "timestamp": datetime.fromtimestamp(
                                    item[0] / 1000
                                ).isoformat(),
                                "open": float(item[1]),
                                "high": float(item[2]),
                                "low": float(item[3]),
                                "close": float(item[4]),
                                "volume": float(item[5]),
                            }
                            candles.append(candle)
                        return candles
                    else:
                        logger.error(f"바이낸스 API 호출 실패: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"바이낸스 캔들 데이터 조회 중 오류: {str(e)}")
            return []

    async def get_upbit_candles(
        self, market: str = "KRW-BTC", interval: str = "1d", limit: int = 100
    ) -> List[Dict[str, Any]]:
        """업비트 캔들 데이터 조회"""
        try:
            url = "https://api.upbit.com/v1/candles"

            # 업비트 interval 포맷 변환
            interval_map = {
                "1d": "days",
                "1h": "minutes/60",
                "4h": "minutes/240",
                "15m": "minutes/15",
            }
            upbit_interval = interval_map.get(interval, "days")

            # API 엔드포인트 구성
            if "minutes" in upbit_interval:
                url += f"/minutes/{upbit_interval.split('/')[1]}"
            else:
                url += f"/{upbit_interval}"

            params = {"market": market, "count": limit}

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        # 업비트 캔들 데이터 포맷 변환
                        return [
                            {
                                "timestamp": candle["candle_date_time_utc"],
                                "open": float(candle["opening_price"]),
                                "high": float(candle["high_price"]),
                                "low": float(candle["low_price"]),
                                "close": float(candle["trade_price"]),
                                "volume": float(candle["candle_acc_trade_volume"]),
                            }
                            for candle in data
                        ]
                    else:
                        logger.error(f"업비트 API 호출 실패: {response.status}")
                        return []

        except Exception as e:
            logger.error(f"업비트 캔들 데이터 조회 중 오류: {str(e)}")
            return []


# 싱글톤 인스턴스 생성
exchange_service = ExchangeRateService()
