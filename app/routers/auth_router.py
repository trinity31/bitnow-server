from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_session
from app.models import User, ErrorResponse
from app.utils.auth import (
    verify_password,
    create_access_token,
    get_password_hash,
    get_current_user,
)
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field, ValidationError
from typing import Optional
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

router = APIRouter()


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    fcm_token: Optional[str] = None


@router.post("/auth/register", tags=["auth"])
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    try:
        # 이메일 중복 체크
        result = await session.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            return JSONResponse(
                status_code=400,
                content={"code": "EMAIL_EXISTS", "message": "이미 등록된 이메일입니다"},
            )

        # 새 사용자 생성
        hashed_password = get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            password=hashed_password,
            fcm_token=user_data.fcm_token,
        )
        session.add(user)
        await session.commit()

        return {"message": "User created successfully"}

    except ValidationError:
        return JSONResponse(
            status_code=400,
            content={"code": "INVALID_INPUT", "message": "잘못된 입력입니다"},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"code": "SERVER_ERROR", "message": "서버 오류가 발생했습니다"},
        )


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/auth/login", tags=["auth"])
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    """사용자 로그인"""
    # 사용자 조회
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/auth/login/json", tags=["auth"])
async def login_json(
    login_data: LoginRequest,
    session: AsyncSession = Depends(get_session),
):
    """JSON 기반 로그인 (모바일 앱용)"""
    # 사용자 조회
    result = await session.execute(select(User).where(User.email == login_data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(login_data.password, user.password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
        )

    # JWT 토큰 생성
    access_token = create_access_token(data={"sub": str(user.id)})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {"id": user.id, "email": user.email, "fcm_token": user.fcm_token},
    }


@router.post("/auth/logout", tags=["auth"])
async def logout(current_user: User = Depends(get_current_user)):
    """사용자 로그아웃

    클라이언트는 저장된 토큰을 삭제해야 합니다.
    서버 측에서는 JWT를 사용하므로 별도의 세션 관리가 필요 없습니다.
    """
    return {"message": "Successfully logged out"}


@router.delete("/auth/me", tags=["auth"])
async def delete_user(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """현재 로그인한 사용자 계정 삭제"""
    try:
        # 사용자의 알림 조건들도 함께 삭제 (cascade)
        await session.delete(current_user)
        await session.commit()
        return {"message": "User account deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete user: {str(e)}")
