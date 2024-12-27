from fastapi import APIRouter, Query
from typing import Optional
from ..services.indicator_service import IndicatorService
from ..constants import (
    DEFAULT_RSI_LENGTH,
    DEFAULT_RSI_INTERVAL,
    DEFAULT_SYMBOL,
    RSI_INTERVALS,
)
import asyncio

router = APIRouter(prefix="/indicator", tags=["indicators"])
indicator_service = IndicatorService()


@router.get("/rsi")
async def get_rsi(
    symbol: str = Query(DEFAULT_SYMBOL, description="암호화폐 심볼 (예: BTC)"),
    interval: str = Query(
        DEFAULT_RSI_INTERVAL, description="캔들 간격 (15m, 1h, 4h, 1d, all)"
    ),
    length: int = Query(DEFAULT_RSI_LENGTH, description="RSI 기간"),
):
    """RSI 값을 조회하는 엔드포인트"""
    if interval == "all":
        # 모든 interval에 대해 RSI 계산
        result = {}
        for key in RSI_INTERVALS.keys():
            try:
                rsi_data = await indicator_service.calculate_rsi(symbol, key, length)
                result[key] = rsi_data
            except Exception as e:
                print(f"Error calculating RSI for {key}: {str(e)}")
                result[key] = {"rsi": 50.0, "signal": "neutral"}
        return result
    else:
        actual_interval = RSI_INTERVALS.get(interval, interval)
        return await indicator_service.calculate_rsi(symbol, actual_interval, length)


@router.get("/dominance")
async def get_btc_dominance():
    """비트코인 도미넌스를 조회하는 엔드포인트"""
    return await indicator_service.get_btc_dominance()


@router.get("/mvrv")
async def get_mvrv():
    """MVRV를 조회하는 엔드포인트"""
    return await indicator_service.get_mvrv()
