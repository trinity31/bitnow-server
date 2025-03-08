from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
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
    locale = Column(String(10), nullable=True)  # 사용자 언어 설정
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    alerts = relationship("Alert", back_populates="user", cascade="all, delete-orphan")
    credits = relationship(
        "Credit", back_populates="user", uselist=False
    )  # one-to-one relationship


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    type = Column(String)  # price, rsi, kimchi_premium, dominance, mvrv, ma
    symbol = Column(String)
    threshold = Column(Float)
    direction = Column(String)  # above, below
    interval = Column(
        String, nullable=True
    )  # RSI용 (15m, 1h, 4h, 1d), MA용 (20, 60, 120, 200)
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


class Credit(Base):
    __tablename__ = "credits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="credits")  # back reference to User


class CreditHistory(Base):
    __tablename__ = "credit_histories"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    amount = Column(Integer)
    type = Column(String)  # "EARN" 또는 "USE"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User")


class FearGreedIndicator(Base):
    __tablename__ = "fear_greed_indicators"

    id = Column(Integer, primary_key=True, index=True)
    value = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<FearGreedIndicator(id={self.id}, value={self.value}, created_at={self.created_at})>"
