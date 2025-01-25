from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_session
from app.services.credit_service import CreditService
from app.utils.auth import get_current_user
from app.services.slack_service import SlackService
from app.constants import CREDIT_PER_AD_VIEW

router = APIRouter(prefix="/credits", tags=["credits"])
slack_service = SlackService()


@router.get("/balance")
async def get_credit_balance(
    current_user=Depends(get_current_user), db: Session = Depends(get_session)
):
    balance = await CreditService.get_user_credit(db, current_user.id)
    return {"balance": balance}


@router.post("/earn/ad-view")
async def earn_credit_from_ad(
    current_user=Depends(get_current_user), db: Session = Depends(get_session)
):
    try:
        new_balance = await CreditService.add_credit_for_ad(db, current_user.id)

        # 슬랙 메시지 전송
        await slack_service.send_message(
            f"사용자 {current_user.email}님이 광고를 시청하고 {CREDIT_PER_AD_VIEW}크레딧을 적립했습니다. "
            f"현재 보유 크레딧: {new_balance}"
        )

        return {"message": "크레딧이 적립되었습니다", "new_balance": new_balance}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "ADD_FAILED",
                "message": "크레딧 적립에 실패했습니다",
            },
        )
