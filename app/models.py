from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base
from pydantic import BaseModel


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String, unique=True)
    password = Column(String)  # 해시된 비밀번호
    fcm_token = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)  # 관리자 여부
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)  # price, rsi, kimchi_premium, dominance, mvrv
    symbol = Column(String)
    threshold = Column(Float)
    direction = Column(String)  # above, below
    interval = Column(String, nullable=True)  # RSI용 (15m, 1h, 4h, 1d)
    currency = Column(String, default="KRW")  # KRW 또는 USD
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    triggered_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="alerts")


class ErrorResponse(BaseModel):
    code: str
    message: str


class MVRVIndicator(Base):
    __tablename__ = "mvrv_indicators"

    id = Column(Integer, primary_key=True)
    value = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
