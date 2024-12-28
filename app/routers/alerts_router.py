from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.services.alert_service import alert_service
from pydantic import BaseModel
from app.utils.auth import get_current_user
from app.models import User

router = APIRouter()


class AlertCreate(BaseModel):
    type: str
    symbol: str
    threshold: float
    direction: str
    interval: str = None


@router.post("/alerts/condition")
async def create_alert_condition(
    alert_data: AlertCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """알림 조건 생성"""
    try:
        alert = await alert_service.create_alert(
            session, current_user.id, alert_data.dict()
        )
        return alert
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/alerts")
async def get_alerts(session: AsyncSession = Depends(get_session)):
    """활성화된 알림 조건 조회"""
    try:
        alerts = await alert_service.get_active_alerts(session)
        return alerts
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
