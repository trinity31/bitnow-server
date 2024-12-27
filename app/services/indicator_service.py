import pandas as pd
import pandas_ta as ta
import requests
import os
from typing import Dict, Optional
from dotenv import load_dotenv
from .exchange_service import exchange_service
from ..constants import (
    DEFAULT_RSI_LENGTH,
    DEFAULT_RSI_INTERVAL,
    DEFAULT_SYMBOL,
    MOCK_DOMINANCE,
    MOCK_MVRV,
    COINMARKETCAP_API_URL,
    RSI_INTERVALS,
)
import numpy as np
import aiohttp
import time
import asyncio

load_dotenv()


class IndicatorService:
    def __init__(self):
        self._last_taapi_call = 0  # 인스턴스 변수로 변경
        self._min_interval = 1.5  # API 호출 간격을 1.5초로 설정

    @staticmethod
    def _calculate_rsi(data: pd.DataFrame, length: int = 14) -> float:
        """RSI 계산 함수 (Wilder's RSI)"""
        # 가격 변화 계산
        delta = data["close"].diff()

        # 상승/하락 구분
        gain = (delta.where(delta > 0, 0)).fillna(0)
        loss = (-delta.where(delta < 0, 0)).fillna(0)

        # Wilder's Smoothing
        avg_gain = gain.ewm(alpha=1 / length, min_periods=length).mean()
        avg_loss = loss.ewm(alpha=1 / length, min_periods=length).mean()

        # RSI 계산
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi.iloc[-1]

    @staticmethod
    async def calculate_rsi(
        symbol: str = DEFAULT_SYMBOL,
        interval: str = DEFAULT_RSI_INTERVAL,
        length: int = DEFAULT_RSI_LENGTH,
    ) -> Dict[str, float]:
        """RSI 계산 함수"""
        try:
            if interval == "all":
                # 모든 interval에 대한 RSI 계산
                result = {}
                for key, value in RSI_INTERVALS.items():
                    try:
                        print(f"Calculating RSI for {key} interval...")
                        candles = await exchange_service.get_candles(
                            symbol, value, length * 2
                        )
                        df = pd.DataFrame(candles)
                        rsi = IndicatorService._calculate_rsi(df, length)

                        if pd.isna(rsi) or not np.isfinite(rsi):
                            result[key] = {"rsi": 50.0, "signal": "neutral"}
                        else:
                            rsi_value = round(float(rsi), 2)
                            # RSI 시그널 판단
                            signal = "neutral"
                            if rsi_value >= 70:
                                signal = "bear"  # 과매수
                            elif rsi_value <= 30:
                                signal = "bull"  # 과매도

                            result[key] = {"rsi": rsi_value, "signal": signal}
                    except Exception as e:
                        print(f"Error calculating RSI for {key}: {str(e)}")
                        result[key] = {"rsi": 50.0, "signal": "neutral"}
                return result
            else:
                candles = await exchange_service.get_candles(
                    symbol, interval, length * 2
                )
                df = pd.DataFrame(candles)
                rsi = IndicatorService._calculate_rsi(df, length)

                if pd.isna(rsi) or not np.isfinite(rsi):
                    return {"rsi": 50.0, "signal": "neutral"}

                rsi_value = round(float(rsi), 2)
                # RSI 시그널 판단
                signal = "neutral"
                if rsi_value >= 70:
                    signal = "bear"  # 과매수
                elif rsi_value <= 30:
                    signal = "bull"  # 과매도

                return {"rsi": rsi_value, "signal": signal}

        except Exception as e:
            print(f"RSI 계산 중 오류 발생: {str(e)}")
            if interval == "all":
                return {
                    key: {"rsi": 50.0, "signal": "neutral"}
                    for key in RSI_INTERVALS.keys()
                }
            return {"rsi": 50.0, "signal": "neutral"}

    @staticmethod
    async def get_btc_dominance() -> Dict[str, float]:
        """비트코인 도미넌스 조회 함수
        CoinMarketCap API를 사용하여 실시간 비트코인 도미넌스를 조회합니다.
        """
        try:
            headers = {
                "X-CMC_PRO_API_KEY": os.getenv("COINMARKETCAP_API_KEY"),
            }

            # 글로벌 메트릭스 데이터 조회
            response = requests.get(
                f"{COINMARKETCAP_API_URL}/global-metrics/quotes/latest", headers=headers
            )

            if response.status_code == 200:
                data = response.json()
                btc_dominance = data["data"]["btc_dominance"]
                return {"dominance": round(float(btc_dominance), 2)}
            else:
                # API 호출 실패시 Mock 데이터 반환
                print(f"CoinMarketCap API 호출 실패: {response.status_code}")
                return {"dominance": MOCK_DOMINANCE}

        except Exception as e:
            print(f"비트코인 도미넌스 조회 중 오류 발생: {str(e)}")
            return {"dominance": MOCK_DOMINANCE}

    @staticmethod
    async def get_mvrv() -> Dict[str, float]:
        """MVRV 조회 함수
        TODO: Glassnode API 연동 필요
        """
        return {"mvrv": MOCK_MVRV}

    async def get_taapi_rsi(
        self,
        symbol: str = DEFAULT_SYMBOL,
        interval: str = DEFAULT_RSI_INTERVAL,
    ) -> Dict[str, float]:
        """Taapi.io에서 RSI 값을 직접 가져오는 함수"""
        try:
            # Rate limiting: 최소 간격으로 API 호출
            current_time = time.time()
            time_since_last_call = current_time - self._last_taapi_call

            if time_since_last_call < self._min_interval:
                wait_time = self._min_interval - time_since_last_call
                print(f"Waiting {wait_time:.2f} seconds before next API call...")
                await asyncio.sleep(wait_time)

            self._last_taapi_call = time.time()

            url = "https://api.taapi.io/rsi"
            params = {
                "secret": os.getenv("TAAPI_SECRET"),
                "exchange": "binance",
                "symbol": f"{symbol}/USDT",
                "interval": interval,
                "backtrack": 0,  # 최신 데이터만 요청
            }

            print(f"Calling Taapi.io API for {interval} interval...")
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        rsi_value = round(float(data["value"]), 2)
                        print(f"Received RSI value: {rsi_value}")
                        return {"rsi": rsi_value}
                    elif response.status == 429:
                        print(
                            "Taapi.io rate limit exceeded, falling back to calculation..."
                        )
                        return await self.calculate_rsi(symbol, interval)
                    else:
                        raise Exception(f"Failed to fetch RSI: {response.status}")

        except Exception as e:
            print(f"RSI 조회 중 오류 발생: {str(e)}")
            return await self.calculate_rsi(symbol, interval)
