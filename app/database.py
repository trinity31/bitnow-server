from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import MetaData
import os
from dotenv import load_dotenv
import logging

load_dotenv()

# 환경 변수로 프로덕션 모드 확인
IS_PRODUCTION = os.getenv("ENVIRONMENT", "dev") == "prod"
DATABASE_URL = os.getenv("PROD_DATABASE_URL" if IS_PRODUCTION else "DATABASE_URL")

# SQLAlchemy 로거 비활성화
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    metadata = MetaData()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
