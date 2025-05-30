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
from app.services.stream_service import stream_service
from app.utils.auth import get_current_user
from app.models import User
from app.services.exchange_service import exchange_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/indicator", tags=["indicators"])
indicator_service = IndicatorService()


# 환율 수동 설정을 위한 요청 모델
class ExchangeRateUpdate(BaseModel):
    rate: float


# MVRV 업데이트를 위한 요청 모델
class MVRVUpdate(BaseModel):
    value: float


# MA 크로스 분석 수정을 위한 요청 모델
class MAAnalysisUpdate(BaseModel):
    trend: str
    description: str


# 공포/탐욕 지수 업데이트를 위한 요청 모델
class FearGreedUpdate(BaseModel):
    value: int
    classification: str = None  # 선택적 분류 필드


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


@router.get("/fear-greed")
async def get_fear_greed_index(
    db: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    현재 공포/탐욕 지수를 조회합니다.

    Returns:
        dict: {
            "value": int,  # 공포/탐욕 지수 값 (0-100)
            "classification": str,  # 분류 (extreme_fear, fear, neutral, greed, extreme_greed)
            "timestamp": str  # 타임스탬프 (ISO 형식)
        }
    """
    return await indicator_service.get_fear_greed_index(db)


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
        # 캐시된 MA 크로스 데이터 가져오기
        ma_data = stream_service.current_prices.get("ma_cross")
        if not ma_data:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "MA_CROSS_NOT_READY",
                    "message": "이동평균선 데이터가 아직 준비되지 않았습니다",
                },
            )
        return ma_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get MA cross data: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "MA_CROSS_FETCH_FAILED",
                "message": "이동평균선 데이터 조회에 실패했습니다",
            },
        )


@router.put("/ma-cross/analysis", response_model=Dict[str, Any])
async def update_ma_analysis(
    data: MAAnalysisUpdate,
    current_user: User = Depends(get_current_user),
):
    """
    MA 크로스 분석 결과를 수정합니다. (관리자 전용)
    """
    try:
        if not current_user.is_admin:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "NOT_ADMIN",
                    "message": "관리자만 접근할 수 있습니다",
                },
            )

        ma_data = stream_service.current_prices.get("ma_cross")
        if not ma_data:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "MA_CROSS_NOT_FOUND",
                    "message": "수정할 MA 크로스 데이터가 없습니다",
                },
            )

        # 분석 결과 업데이트
        ma_data["market_diagnosis"] = {
            "trend": data.trend,
            "description": data.description,
        }
        stream_service.current_prices["ma_cross"] = ma_data

        logger.info(f"MA analysis updated by admin: {current_user.email}")
        return ma_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update MA analysis: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPDATE_FAILED",
                "message": "MA 크로스 분석 수정에 실패했습니다",
            },
        )


@router.put("/exchange-rate", response_model=Dict[str, Any])
async def update_exchange_rate(
    data: ExchangeRateUpdate, current_user: User = Depends(get_current_user)
):
    """환율 수동 설정 (관리자 전용)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_ADMIN", "message": "관리자만 접근할 수 있습니다"},
        )

    return await exchange_service.set_manual_rate(data.rate)


@router.delete("/exchange-rate", response_model=Dict[str, Any])
async def reset_exchange_rate(current_user: User = Depends(get_current_user)):
    """수동 설정 환율 초기화 (관리자 전용)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_ADMIN", "message": "관리자만 접근할 수 있습니다"},
        )

    return await exchange_service.reset_manual_rate()


@router.get("/exchange-rate", response_model=Dict[str, Any])
async def get_exchange_rate():
    """현재 환율 조회"""
    rate = await exchange_service.get_usd_krw_rate()
    return {
        "rate": rate,
        "is_manual": exchange_service.manual_rate is not None,
        "last_update": (
            exchange_service.last_update.isoformat()
            if exchange_service.last_update
            else None
        ),
        "manual_update": (
            exchange_service.manual_rate_time.isoformat()
            if exchange_service.manual_rate_time
            else None
        ),
    }


@router.put("/fear-greed", response_model=Dict[str, Any])
async def update_fear_greed_index(
    data: FearGreedUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_session),
):
    """공포/탐욕 지수를 수동으로 업데이트합니다. (관리자 전용)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "NOT_ADMIN", "message": "관리자만 접근할 수 있습니다"},
        )

    try:
        # 값에 따른 분류 자동 설정 (사용자가 제공하지 않은 경우)
        if data.classification is None:
            if data.value <= 20:
                data.classification = "extreme_fear"
            elif data.value <= 40:
                data.classification = "fear"
            elif data.value <= 60:
                data.classification = "neutral"
            elif data.value <= 80:
                data.classification = "greed"
            else:
                data.classification = "extreme_greed"

        # 지수 업데이트
        result = await indicator_service.update_fear_greed(db, data.value)

        # 스트림 서비스의 캐시 업데이트
        stream_service.current_prices["fear_greed"] = {
            "value": result["value"],
            "classification": result["classification"],
            "timestamp": result["timestamp"],
        }

        logger.info(f"Fear & Greed index updated by admin: {current_user.email}")
        return result

    except Exception as e:
        logger.error(f"Failed to update Fear & Greed index: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPDATE_FAILED",
                "message": "공포/탐욕 지수 업데이트에 실패했습니다",
            },
        )
