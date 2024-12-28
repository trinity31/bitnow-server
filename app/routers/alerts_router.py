from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.services.alert_service import alert_service
from pydantic import BaseModel
from app.utils.auth import get_current_user
from app.models import User, Alert
from sqlalchemy import select

router = APIRouter()


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
async def get_alerts(session: AsyncSession = Depends(get_session)):
    """활성화된 알림 조건 조회"""
    try:
        alerts = await alert_service.get_active_alerts(session)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


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
