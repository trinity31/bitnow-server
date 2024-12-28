import pandas as pd
import pandas_ta as ta
import requests
import os
from typing import Dict, Optional, Any, List
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
    GLASSNODE_API_URL,
)
import numpy as np
import aiohttp
import time
import asyncio
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

load_dotenv()


class IndicatorService:
    def __init__(self):
        self.coinmarketcap_api_key = os.getenv("COINMARKETCAP_API_KEY")
        self.glassnode_api_key = os.getenv("GLASSNODE_API_KEY")

    async def calculate_rsi(
        self, symbol: str = "BTC", interval: str = "15m", length: int = 14
    ) -> Dict[str, Any]:
        """RSI 계산"""
        try:
            # 캔들 데이터 가져오기 (RSI 계산을 위해 더 많은 데이터 필요)
            candles = await exchange_service.get_candles(symbol, interval, length * 3)

            # 종가 데이터로 DataFrame 생성
            closes = [candle["close"] for candle in candles]
            df = pd.DataFrame(closes, columns=["close"])

            # RSI 계산
            rsi = ta.rsi(df["close"], length=length).iloc[-1]

            # RSI 값이 NaN인 경우 처리
            if pd.isna(rsi):
                return {"rsi": 50.0, "signal": "neutral"}

            # RSI 값에 따른 신호 결정
            signal = "neutral"
            if rsi >= 70:
                signal = "overbought"
            elif rsi <= 30:
                signal = "oversold"

            return {"rsi": round(float(rsi), 2), "signal": signal}

        except Exception as e:
            logger.error(f"RSI 계산 중 오류 발생: {str(e)}")
            return {"rsi": 50.0, "signal": "neutral"}  # 에러 시 기본값 반환

    async def get_btc_dominance(self) -> Dict[str, Any]:
        """비트코인 도미넌스 조회"""
        try:
            url = f"{COINMARKETCAP_API_URL}/global-metrics/quotes/latest"
            headers = {
                "X-CMC_PRO_API_KEY": self.coinmarketcap_api_key,
                "Accept": "application/json",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        btc_dominance = data["data"]["btc_dominance"]
                        return {
                            "dominance": round(float(btc_dominance), 2),
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        logger.warning("CoinMarketCap API 호출 실패, 기본값 사용")
                        return {
                            "dominance": MOCK_DOMINANCE,
                            "timestamp": datetime.now().isoformat(),
                        }

        except Exception as e:
            logger.error(f"도미넌스 조회 중 오류 발생: {str(e)}")
            return {
                "dominance": MOCK_DOMINANCE,
                "timestamp": datetime.now().isoformat(),
            }

    async def get_mvrv(self) -> Dict[str, Any]:
        """MVRV(Market Value to Realized Value) 조회"""
        try:
            url = f"{GLASSNODE_API_URL}/metrics/market/mvrv"
            params = {
                "api_key": self.glassnode_api_key,
                "asset": "BTC",
                "timestamp_format": "humanized",
            }

            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data and len(data) > 0:
                            latest_mvrv = data[-1]["value"]  # 가장 최근 값
                            return {
                                "mvrv": round(float(latest_mvrv), 2),
                                "timestamp": datetime.now().isoformat(),
                            }

                    logger.warning("Glassnode API 호출 실패, 기본값 사용")
                    return {
                        "mvrv": MOCK_MVRV,
                        "timestamp": datetime.now().isoformat(),
                    }

        except Exception as e:
            logger.error(f"MVRV 조회 중 오류 발생: {str(e)}")
            return {
                "mvrv": MOCK_MVRV,
                "timestamp": datetime.now().isoformat(),
            }


# 싱글톤 인스턴스 생성
indicator_service = IndicatorService()
