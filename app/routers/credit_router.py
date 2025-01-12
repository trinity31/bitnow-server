from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_session
from app.services.credit_service import CreditService
from app.utils.auth import get_current_user

router = APIRouter(prefix="/credits", tags=["credits"])


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
    new_balance = await CreditService.add_credit_for_ad(db, current_user.id)
    return {"message": "크레딧이 적립되었습니다", "new_balance": new_balance}
