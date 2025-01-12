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
        # 통화 검증
        if alert_data.type == "price" and alert_data.currency not in ["KRW", "USD"]:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "INVALID_CURRENCY",
                    "message": "통화는 KRW 또는 USD만 가능합니다",
                },
            )

        # 크레딧 차감 시도
        try:
            await CreditService.deduct_credit(session, current_user.id)
        except HTTPException as e:
            raise HTTPException(
                status_code=400, detail="크레딧이 부족하여 알림을 설정할 수 없습니다"
            )

        # 알림 생성
        alert = await alert_service.create_alert(
            session, current_user.id, alert_data.dict()
        )
        return alert

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "CREATE_FAILED",
                "message": "알림 조건 생성에 실패했습니다",
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
