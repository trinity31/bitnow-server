from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy import MetaData
import os
from dotenv import load_dotenv
import logging

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./bitnow.db")

# SQLAlchemy 로거 비활성화
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    metadata = MetaData()


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session
