from fastapi import APIRouter, Query, Depends, HTTPException
from typing import Optional, Dict, Any
from ..services.indicator_service import IndicatorService
from ..constants import (
    DEFAULT_RSI_LENGTH,
    DEFAULT_RSI_INTERVAL,
    DEFAULT_SYMBOL,
    RSI_INTERVALS,
)
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from pydantic import BaseModel
from app.services.price_service import check_ma_cross_all
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicator", tags=["indicators"])
indicator_service = IndicatorService()


# MVRV 업데이트를 위한 요청 모델
class MVRVUpdate(BaseModel):
    value: float


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
async def get_mvrv(db: AsyncSession = Depends(get_session)) -> Dict[str, Any]:
    """
    현재 MVRV 값을 조회합니다.

    Returns:
        dict: {
            "mvrv": float,  # MVRV 값
            "timestamp": str  # 타임스탬프 (ISO 형식)
        }
    """
    return await indicator_service.get_mvrv(db)


@router.post("/mvrv")
async def create_mvrv(
    data: MVRVUpdate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    새로운 MVRV 값을 생성합니다.

    Args:
        data (MVRVUpdate): 생성할 MVRV 데이터
            - value (float): MVRV 값

    Returns:
        dict: {
            "mvrv": float,  # 생성된 MVRV 값
            "timestamp": str  # 타임스탬프 (ISO 형식)
        }
    """
    try:
        return await indicator_service.create_mvrv(db, data.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/mvrv")
async def update_mvrv(
    data: MVRVUpdate,
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    가장 최근 MVRV 값을 업데이트합니다.

    Args:
        data (MVRVUpdate): 업데이트할 MVRV 데이터
            - value (float): 새로운 MVRV 값

    Returns:
        dict: {
            "mvrv": float,  # 업데이트된 MVRV 값
            "timestamp": str  # 타임스탬프 (ISO 형식)
        }
    """
    try:
        return await indicator_service.update_mvrv(db, data.value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mvrv")
async def delete_mvrv(
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    가장 최근 MVRV 값을 삭제합니다.

    Returns:
        dict: {
            "mvrv": float,  # 삭제된 MVRV 값
            "timestamp": str  # 타임스탬프 (ISO 형식)
        }
    """
    try:
        return await indicator_service.delete_latest_mvrv(db)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ma-cross", response_model=Dict[str, Any])
async def get_ma_cross():
    """
    BTC/USDT의 20일, 60일, 120일, 200일 이동평균선 돌파 여부를 반환
    """
    try:
        ma_data = await check_ma_cross_all()
        return ma_data
    except Exception as e:
        logger.error(f"Failed to get MA cross data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "MA_CROSS_FETCH_FAILED",
                "message": "이동평균선 데이터 조회에 실패했습니다",
            },
        )
