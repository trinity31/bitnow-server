from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import Credit, CreditHistory
from app.constants import CREDIT_PER_AD_VIEW, MIN_CREDIT_FOR_ALERT


class CreditService:
    @staticmethod
    async def get_user_credit(db: AsyncSession, user_id: int) -> int:
        query = select(Credit).filter(Credit.user_id == user_id)
        result = await db.execute(query)
        credit = result.scalar_one_or_none()

        if not credit:
            credit = Credit(user_id=user_id, amount=0)
            db.add(credit)
            await db.commit()
        return credit.amount

    @staticmethod
    async def deduct_credit(db: AsyncSession, user_id: int) -> bool:
        query = select(Credit).filter(Credit.user_id == user_id)
        result = await db.execute(query)
        credit = result.scalar_one_or_none()

        if not credit or credit.amount < MIN_CREDIT_FOR_ALERT:
            raise HTTPException(status_code=400, detail="크레딧이 부족합니다")

        credit.amount -= MIN_CREDIT_FOR_ALERT

        history = CreditHistory(
            user_id=user_id, amount=-MIN_CREDIT_FOR_ALERT, type="USE"
        )

        db.add(history)
        await db.commit()
        return True

    @staticmethod
    async def add_credit_for_ad(db: AsyncSession, user_id: int) -> int:
        query = select(Credit).filter(Credit.user_id == user_id)
        result = await db.execute(query)
        credit = result.scalar_one_or_none()

        if not credit:
            credit = Credit(user_id=user_id, amount=0)
            db.add(credit)

        credit.amount += CREDIT_PER_AD_VIEW

        history = CreditHistory(user_id=user_id, amount=CREDIT_PER_AD_VIEW, type="EARN")

        db.add(history)
        await db.commit()
        return credit.amount
