from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.services.alert_service import alert_service
from pydantic import BaseModel
from app.utils.auth import get_current_user
from app.models import User, Alert
from sqlalchemy import select
import logging
from datetime import datetime
from app.services.credit_service import CreditService
from app.constants.messages import ERROR_MESSAGES

router = APIRouter()
logger = logging.getLogger(__name__)


class AlertCreate(BaseModel):
    type: str
    symbol: str
    threshold: float
    direction: str
    interval: str = None
    currency: str = "KRW"  # KRW 또는 USD, 기본값은 KRW


@router.post("/alerts/condition")
async def create_alert_condition(
    alert_data: AlertCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """알림 조건 생성"""
    try:
        locale = current_user.locale or "en"
        messages = ERROR_MESSAGES.get(locale, ERROR_MESSAGES["en"])

        # MA 알림 유효성 검사
        if alert_data.type == "ma":
            if alert_data.interval not in ["20", "60", "120", "200"]:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INVALID_MA_INTERVAL",
                        "message": "MA 알림은 20, 60, 120, 200일만 가능합니다",
                    },
                )
            # MA 알림은 threshold를 0으로 설정
            alert_data.threshold = 0.0

        # 통화 검증
        if alert_data.type == "price" and alert_data.currency not in ["KRW", "USD"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_CURRENCY",
                    "message": messages["INVALID_CURRENCY"],
                },
            )

        # 동일한 조건의 알림이 있는지 확인 (비활성화된 알림 포함)
        query = select(Alert).where(
            Alert.user_id == current_user.id,
            Alert.type == alert_data.type,
            Alert.symbol == alert_data.symbol,
            Alert.threshold == alert_data.threshold,
            Alert.direction == alert_data.direction,
        )

        if alert_data.type == "price":
            query = query.where(Alert.currency == alert_data.currency)
        if alert_data.type in ["rsi", "ma"]:
            query = query.where(Alert.interval == alert_data.interval)

        result = await session.execute(query)
        existing_alert = result.scalar_one_or_none()

        if existing_alert:
            # 비활성화된 알림이 있는 경우 재활성화 안내
            if not existing_alert.is_active:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "INACTIVE_ALERT_EXISTS",
                        "message": messages["INACTIVE_ALERT_EXISTS"],
                        "alert_id": existing_alert.id,
                    },
                )
            # 활성화된 알림이 있는 경우
            else:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "DUPLICATE_ALERT",
                        "message": messages["DUPLICATE_ALERT"],
                        "alert_id": existing_alert.id,
                    },
                )

        # 크레딧 차감 시도
        try:
            await CreditService.deduct_credit(session, current_user.id)
        except HTTPException as e:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "CREATE_FAILED",
                    "message": "크레딧이 부족하여 알림을 설정할 수 없습니다",
                },
            )

        # 알림 생성
        alert = await alert_service.create_alert(
            session, current_user.id, alert_data.dict()
        )
        return alert

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CREATE_FAILED",
                "message": messages["CREATE_FAILED"],
            },
        )


@router.get("/alerts")
async def get_alerts(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """사용자의 모든 알림 조건 조회 (비활성화된 알림 포함)"""
    try:
        # 모든 알림 조회
        result = await session.execute(
            select(Alert).where(Alert.user_id == current_user.id)
        )
        alerts = result.scalars().all()

        # 알림 목록을 활성화 상태와 생성 시간 순으로 정렬
        sorted_alerts = sorted(
            alerts,
            key=lambda x: (
                not x.is_active,
                x.created_at.timestamp() if x.created_at else 0,
            ),
            reverse=True,
        )

        return sorted_alerts
    except Exception as e:
        logger.error(f"Failed to get alerts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "FETCH_FAILED",
                "message": "알림 조건 조회에 실패했습니다",
            },
        )


@router.delete("/alerts/{alert_id}", tags=["alerts"])
async def delete_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """알림 조건 삭제"""
    try:
        # 알림 조건 조회
        result = await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ALERT_NOT_FOUND",
                    "message": "알림 조건을 찾을 수 없습니다",
                },
            )

        # 알림 조건 삭제
        await session.delete(alert)
        await session.commit()

        return {"message": "Alert condition deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "DELETE_FAILED",
                "message": "알림 조건 삭제에 실패했습니다",
            },
        )


@router.patch("/alerts/{alert_id}/toggle", tags=["alerts"])
async def toggle_alert(
    alert_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """알림 활성화 상태 토글"""
    try:
        # 알림 조건 조회
        result = await session.execute(
            select(Alert).where(Alert.id == alert_id, Alert.user_id == current_user.id)
        )
        alert = result.scalar_one_or_none()

        if not alert:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "ALERT_NOT_FOUND",
                    "message": "알림 조건을 찾을 수 없습니다",
                },
            )

        # 알림 상태 토글
        alert.is_active = not alert.is_active
        alert.updated_at = datetime.now()
        await session.commit()

        # 캐시 갱신
        alert_service.last_cache_update = None
        await alert_service.refresh_cache(session)

        status = "활성화" if alert.is_active else "비활성화"
        logger.info(f"Alert {alert_id} {status} 상태로 변경됨")

        return {
            "id": alert.id,
            "is_active": alert.is_active,
            "message": f"알림이 {status}되었습니다",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to toggle alert: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPDATE_FAILED",
                "message": "알림 상태 변경에 실패했습니다",
            },
        )
