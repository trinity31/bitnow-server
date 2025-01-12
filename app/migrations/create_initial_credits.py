import asyncio
from sqlalchemy import select
from app.models import User, Credit
from app.constants import INITIAL_CREDIT_AMOUNT
from app.database import get_session


async def create_initial_credits():
    async for db in get_session():
        try:
            # 크레딧이 없는 모든 사용자 조회
            query = select(User).filter(~User.credits.has())
            result = await db.execute(query)
            users_without_credits = result.scalars().all()

            # 각 사용자에 대해 초기 크레딧 생성
            for user in users_without_credits:
                credit = Credit(user_id=user.id, amount=INITIAL_CREDIT_AMOUNT)
                db.add(credit)
                print(f"Created initial credits for user {user.id}")

            await db.commit()
            print(
                f"Successfully created credits for {len(users_without_credits)} users"
            )

        except Exception as e:
            print(f"Error creating initial credits: {str(e)}")
            await db.rollback()


if __name__ == "__main__":
    asyncio.run(create_initial_credits())
