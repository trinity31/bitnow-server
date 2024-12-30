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
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.sql import desc
from app.models import MVRVIndicator

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

    async def get_mvrv(self, db: AsyncSession) -> Dict[str, Any]:
        """MVRV(Market Value to Realized Value) 조회"""
        try:
            # DB에서 최신 MVRV 값 조회
            query = (
                select(MVRVIndicator).order_by(desc(MVRVIndicator.created_at)).limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            print("latest", latest)

            if latest:
                return {
                    "mvrv": round(float(latest.value), 2),
                    "timestamp": latest.created_at.isoformat(),
                }

            # DB에 값이 없으면 기본값 반환
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

    async def create_mvrv(self, db: AsyncSession, value: float) -> Dict[str, Any]:
        """새로운 MVRV 값을 생성합니다."""
        try:
            new_mvrv = MVRVIndicator(value=value)
            db.add(new_mvrv)
            await db.commit()
            await db.refresh(new_mvrv)

            return {
                "mvrv": round(float(new_mvrv.value), 2),
                "timestamp": new_mvrv.created_at.isoformat(),
            }
        except Exception as e:
            await db.rollback()
            logger.error(f"MVRV 생성 중 오류 발생: {str(e)}")
            raise

    async def update_mvrv(self, db: AsyncSession, value: float) -> Dict[str, Any]:
        """가장 최근 MVRV 값을 업데이트합니다."""
        try:
            # 가장 최근 MVRV 레코드 조회
            query = (
                select(MVRVIndicator).order_by(desc(MVRVIndicator.created_at)).limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            if latest:
                # 기존 레코드 업데이트
                latest.value = value
                await db.commit()
                await db.refresh(latest)

                return {
                    "mvrv": round(float(latest.value), 2),
                    "timestamp": latest.created_at.isoformat(),
                }
            else:
                # 레코드가 없으면 새로 생성
                return await self.create_mvrv(db, value)

        except Exception as e:
            await db.rollback()
            logger.error(f"MVRV 업데이트 중 오류 발생: {str(e)}")
            raise

    async def delete_latest_mvrv(self, db: AsyncSession) -> Dict[str, Any]:
        """가장 최근 MVRV 값을 삭제합니다."""
        try:
            # 가장 최근 MVRV 레코드 조회
            query = (
                select(MVRVIndicator).order_by(desc(MVRVIndicator.created_at)).limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            if latest:
                # 삭제할 MVRV 정보 저장
                deleted_info = {
                    "mvrv": round(float(latest.value), 2),
                    "timestamp": latest.created_at.isoformat(),
                }
                # 레코드 삭제
                await db.delete(latest)
                await db.commit()
                return deleted_info
            else:
                raise HTTPException(
                    status_code=404, detail="삭제할 MVRV 레코드가 없습니다."
                )

        except Exception as e:
            await db.rollback()
            logger.error(f"MVRV 삭제 중 오류 발생: {str(e)}")
            raise


# 싱글톤 인스턴스 생성
indicator_service = IndicatorService()
