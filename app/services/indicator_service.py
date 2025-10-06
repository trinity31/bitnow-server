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
    MOCK_FEAR_GREED_INDEX,
    COINMARKETCAP_API_URL,
    RSI_INTERVALS,
    FEAR_GREED_API_URL,
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
from app.models import MVRVIndicator, FearGreedIndicator

logger = logging.getLogger(__name__)

load_dotenv()


class IndicatorService:
    def __init__(self):
        self.coinmarketcap_api_key = os.getenv("COINMARKETCAP_API_KEY")
        # self.glassnode_api_key = os.getenv("GLASSNODE_API_KEY")

    async def calculate_rsi(
        self, symbol: str = "BTC", interval: str = "15m", length: int = 14
    ) -> Dict[str, Any]:
        """RSI 계산"""
        try:
            # 캔들 데이터 가져오기 (RSI 계산을 위해 더 많은 데이터 필요)
            # length * 3 대신 더 많은 데이터를 가져오도록 수정
            candle_count = {
                "15m": 100,  # 15분봉 100개
                "1h": 100,  # 1시간봉 100개
                "4h": 100,  # 4시간봉 100개
                "1d": 100,  # 일봉 100개
            }

            count = candle_count.get(interval, 100)
            candles = await exchange_service.get_candles(symbol, interval, count)

            if not candles:
                logger.error(f"캔들 데이터를 가져오지 못했습니다. interval: {interval}")
                return {"rsi": 50.0, "signal": "neutral"}

            # 종가 데이터로 DataFrame 생성
            closes = [float(candle["close"]) for candle in candles]
            df = pd.DataFrame(closes, columns=["close"])

            # RSI 계산
            rsi = ta.rsi(df["close"], length=length)
            current_rsi = rsi.iloc[-1]

            # RSI 값이 NaN인 경우 처리
            if pd.isna(current_rsi):
                logger.warning(f"RSI 계산 결과가 NaN입니다. interval: {interval}")
                return {"rsi": 50.0, "signal": "neutral"}

            # RSI 값에 따른 신호 결정
            signal = "neutral"
            if current_rsi >= 70:
                signal = "overbought"
            elif current_rsi <= 30:
                signal = "oversold"

            logger.debug(f"RSI 계산 완료: {interval} = {round(float(current_rsi), 2)}")
            return {"rsi": round(float(current_rsi), 2), "signal": signal}

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

    async def get_fear_greed_index(self, db: AsyncSession) -> Dict[str, Any]:
        """공포/탐욕 지수 조회"""
        try:
            # DB에서 최신 공포/탐욕 지수 값 조회
            query = (
                select(FearGreedIndicator)
                .order_by(desc(FearGreedIndicator.created_at))
                .limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            # 오늘 날짜의 데이터가 있으면 반환
            if latest and latest.created_at.date() == datetime.now().date():
                return {
                    "value": latest.value,
                    "classification": self._get_fear_greed_classification(latest.value),
                    "timestamp": latest.created_at.isoformat(),
                }

            # DB에 오늘 데이터가 없으면 API에서 가져오기
            url = FEAR_GREED_API_URL

            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        fear_greed_value = int(data["data"][0]["value"])

                        # DB에 저장
                        new_fear_greed = FearGreedIndicator(value=fear_greed_value)
                        db.add(new_fear_greed)
                        await db.commit()
                        await db.refresh(new_fear_greed)

                        return {
                            "value": fear_greed_value,
                            "classification": self._get_fear_greed_classification(
                                fear_greed_value
                            ),
                            "timestamp": datetime.now().isoformat(),
                        }
                    else:
                        logger.warning("Fear & Greed API 호출 실패, 기본값 사용")
                        return {
                            "value": MOCK_FEAR_GREED_INDEX,
                            "classification": self._get_fear_greed_classification(
                                MOCK_FEAR_GREED_INDEX
                            ),
                            "timestamp": datetime.now().isoformat(),
                        }

        except Exception as e:
            logger.error(f"공포/탐욕 지수 조회 중 오류 발생: {str(e)}")
            return {
                "value": MOCK_FEAR_GREED_INDEX,
                "classification": self._get_fear_greed_classification(
                    MOCK_FEAR_GREED_INDEX
                ),
                "timestamp": datetime.now().isoformat(),
            }

    def _get_fear_greed_classification(self, value: int) -> str:
        """공포/탐욕 지수 값에 따른 분류 반환"""
        if value <= 24:
            return "extreme_fear"
        elif value <= 44:
            return "fear"
        elif value <= 54:
            return "neutral"
        elif value <= 74:
            return "greed"
        else:
            return "extreme_greed"

    async def get_eth_btc_ratio(self) -> Dict[str, Any]:
        """ETH/BTC 비율 조회"""
        try:
            async with aiohttp.ClientSession() as session:
                # ETHUSDT 가격 조회
                eth_url = "https://api.binance.com/api/v3/ticker/price"
                eth_params = {"symbol": "ETHUSDT"}
                async with session.get(eth_url, params=eth_params) as response:
                    if response.status == 200:
                        eth_data = await response.json()
                        eth_price = float(eth_data["price"])
                    else:
                        logger.warning("바이낸스 ETHUSDT 가격 조회 실패")
                        return {
                            "ratio": 0.0,
                            "timestamp": datetime.now().isoformat(),
                        }

                # BTCUSDT 가격 조회
                btc_url = "https://api.binance.com/api/v3/ticker/price"
                btc_params = {"symbol": "BTCUSDT"}
                async with session.get(btc_url, params=btc_params) as response:
                    if response.status == 200:
                        btc_data = await response.json()
                        btc_price = float(btc_data["price"])
                    else:
                        logger.warning("바이낸스 BTCUSDT 가격 조회 실패")
                        return {
                            "ratio": 0.0,
                            "timestamp": datetime.now().isoformat(),
                        }

                # ETH/BTC 비율 계산
                if btc_price > 0:
                    ratio = eth_price / btc_price
                    return {
                        "ratio": round(ratio, 6),
                        "timestamp": datetime.now().isoformat(),
                    }
                else:
                    logger.error("BTC 가격이 0입니다")
                    return {
                        "ratio": 0.0,
                        "timestamp": datetime.now().isoformat(),
                    }

        except Exception as e:
            logger.error(f"ETH/BTC 비율 조회 중 오류 발생: {str(e)}")
            return {
                "ratio": 0.0,
                "timestamp": datetime.now().isoformat(),
            }

    async def create_fear_greed(self, db: AsyncSession, value: int) -> Dict[str, Any]:
        """새로운 공포/탐욕 지수 값을 생성합니다."""
        try:
            new_fear_greed = FearGreedIndicator(value=value)
            db.add(new_fear_greed)
            await db.commit()
            await db.refresh(new_fear_greed)

            return {
                "value": new_fear_greed.value,
                "classification": self._get_fear_greed_classification(
                    new_fear_greed.value
                ),
                "timestamp": new_fear_greed.created_at.isoformat(),
            }
        except Exception as e:
            await db.rollback()
            logger.error(f"공포/탐욕 지수 생성 중 오류 발생: {str(e)}")
            raise

    async def update_fear_greed(self, db: AsyncSession, value: int) -> Dict[str, Any]:
        """가장 최근 공포/탐욕 지수 값을 업데이트합니다."""
        try:
            # 가장 최근 공포/탐욕 지수 레코드 조회
            query = (
                select(FearGreedIndicator)
                .order_by(desc(FearGreedIndicator.created_at))
                .limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            if latest:
                # 기존 레코드 업데이트
                latest.value = value
                await db.commit()
                await db.refresh(latest)

                return {
                    "value": latest.value,
                    "classification": self._get_fear_greed_classification(latest.value),
                    "timestamp": latest.created_at.isoformat(),
                }
            else:
                # 레코드가 없으면 새로 생성
                return await self.create_fear_greed(db, value)

        except Exception as e:
            await db.rollback()
            logger.error(f"공포/탐욕 지수 업데이트 중 오류 발생: {str(e)}")
            raise

    async def delete_latest_fear_greed(self, db: AsyncSession) -> Dict[str, Any]:
        """가장 최근 공포/탐욕 지수 값을 삭제합니다."""
        try:
            # 가장 최근 공포/탐욕 지수 레코드 조회
            query = (
                select(FearGreedIndicator)
                .order_by(desc(FearGreedIndicator.created_at))
                .limit(1)
            )
            result = await db.execute(query)
            latest = result.scalar_one_or_none()

            if latest:
                # 삭제할 공포/탐욕 지수 정보 저장
                deleted_info = {
                    "value": latest.value,
                    "classification": self._get_fear_greed_classification(latest.value),
                    "timestamp": latest.created_at.isoformat(),
                }
                # 레코드 삭제
                await db.delete(latest)
                await db.commit()
                return deleted_info
            else:
                raise HTTPException(
                    status_code=404, detail="삭제할 공포/탐욕 지수 레코드가 없습니다."
                )

        except Exception as e:
            await db.rollback()
            logger.error(f"공포/탐욕 지수 삭제 중 오류 발생: {str(e)}")
            raise


# 싱글톤 인스턴스 생성
indicator_service = IndicatorService()
