import aiohttp
from typing import Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.constants import DEFAULT_USD_KRW_RATE, CACHE_DURATION_HOURS
import pandas as pd
from typing import List, Dict, Any

# .env 파일에서 환경변수 로드
load_dotenv()


class ExchangeRateService:
    def __init__(self):
        self.base_url = (
            "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
        )
        self.api_key = os.getenv("EXCHANGE_API_KEY")
        self._cached_rate: Optional[float] = None
        self._last_updated: Optional[datetime] = None

    def _is_cache_valid(self) -> bool:
        """캐시가 유효한지 확인합니다."""
        return (
            self._cached_rate is not None
            and self._last_updated is not None
            and datetime.now() - self._last_updated
            < timedelta(hours=CACHE_DURATION_HOURS)
        )

    def _update_cache(self, rate: float) -> None:
        """환율 캐시를 업데이트합니다."""
        self._cached_rate = rate
        self._last_updated = datetime.now()
        print(f"조회된 환율: {rate}")

    async def get_usd_krw_rate(self) -> float:
        """USD/KRW 환율을 조회합니다. 1시간 캐시를 사용합니다."""
        if self._is_cache_valid():
            return self._cached_rate

        # 오늘 날짜로 시도
        today = datetime.now()
        rate = await self._fetch_exchange_rate(today)

        # 오늘 데이터가 없으면 어제 날짜로 재시도
        if rate is None:
            yesterday = today - timedelta(days=1)
            rate = await self._fetch_exchange_rate(yesterday)

            # 어제 데이터도 없으면 기본값 사용
            if rate is None:
                print("환율 데이터를 찾을 수 없습니다. 기본값을 사용합니다.")
                return DEFAULT_USD_KRW_RATE

        return rate

    async def _fetch_exchange_rate(self, date: datetime) -> Optional[float]:
        """특정 날짜의 환율을 조회합니다."""
        params = {
            "authkey": self.api_key,
            "searchdate": date.strftime("%Y%m%d"),
            "data": "AP01",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.base_url, params=params) as response:
                    print(f"Fetching exchange rate for {date.strftime('%Y-%m-%d')}")
                    print("Response status:", response.status)

                    if response.status != 200:
                        return None

                    data = await response.json()
                    print("Response data:", data)

                    if not data or not isinstance(data, list):
                        return None

                    for item in data:
                        if item.get("cur_unit") == "USD":
                            rate = float(item["tts"].replace(",", ""))
                            self._update_cache(rate)
                            return rate

                    return None

        except Exception as e:
            print(f"환율 조회 중 오류 발생: {str(e)}")
            return None

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


# 싱글톤 인스턴스 생성
exchange_service = ExchangeRateService()
