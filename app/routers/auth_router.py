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
from typing import Optional, Dict, Any
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import os
from dotenv import load_dotenv
import logging

load_dotenv()

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "your-secret-key")

router = APIRouter()

logger = logging.getLogger(__name__)


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    fcm_token: Optional[str] = None


@router.post("/auth/register", tags=["auth"])
async def register(user_data: UserCreate, session: AsyncSession = Depends(get_session)):
    try:
        # 이메일 중복 체크
        existing_user = await get_user_by_email(session, user_data.email)
        if existing_user:
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
    try:
        # 사용자 조회
        result = await session.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()

        logger.info(f"로그인 시도: {login_data.email}")

        if not user:
            logger.error(f"사용자를 찾을 수 없음: {login_data.email}")
            raise HTTPException(
                status_code=401, detail="이메일 또는 비밀번호가 잘못되었습니다"
            )

        # 비밀번호 검증
        if not verify_password(login_data.password, user.password):
            logger.error(f"비밀번호 불일치: {login_data.email}")
            raise HTTPException(
                status_code=401, detail="이메일 또는 비밀번호가 잘못되었습니다"
            )

        # JWT 토큰 생성
        access_token = create_access_token(data={"sub": str(user.id)})
        logger.info(f"로그인 성공: {login_data.email}")

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "fcm_token": user.fcm_token,
                "is_admin": user.is_admin,
            },
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"로그인 중 오류 발생: {str(e)}")
        raise HTTPException(status_code=500, detail="서버 오류가 발생했습니다")


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


class FCMTokenUpdate(BaseModel):
    fcm_token: str


@router.put("/auth/fcm-token", tags=["auth"])
async def update_fcm_token(
    token_data: FCMTokenUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """FCM 토큰 업데이트"""
    try:
        current_user.fcm_token = token_data.fcm_token
        await session.commit()
        return {"message": "FCM token updated successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPDATE_FAILED",
                "message": "FCM 토큰 업데이트에 실패했습니다",
            },
        )


# 관리자 생성 요청 모델
class AdminUserCreate(BaseModel):
    email: str
    password: str
    admin_secret: str  # 관리자 생성을 위한 시크릿 키


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """이메일로 사용자를 조회합니다."""
    query = select(User).where(User.email == email)
    result = await db.execute(query)
    return result.scalar_one_or_none()


@router.post("/admin/signup")
async def create_admin(
    user_data: AdminUserCreate, db: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    관리자 권한을 가진 사용자를 생성합니다.
    시크릿 키가 필요합니다.
    """
    try:
        # 시크릿 키 확인
        if user_data.admin_secret != ADMIN_SECRET_KEY:
            raise HTTPException(
                status_code=403, detail="잘못된 관리자 시크릿 키입니다."
            )

        # 이메일 중복 체크
        existing_user = await get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 존재하는 이메일입니다.")

        try:
            # 비밀번호 해시화
            hashed_password = get_password_hash(user_data.password)

            # 관리자 사용자 생성
            new_user = User(
                email=user_data.email,
                password=hashed_password,
                is_admin=True,
            )
            db.add(new_user)
            await db.commit()
            await db.refresh(new_user)

            logger.info(f"관리자 계정 생성 성공: {new_user.email}")

            return {
                "id": new_user.id,
                "email": new_user.email,
                "is_admin": new_user.is_admin,
            }

        except Exception as db_error:
            await db.rollback()
            logger.error(f"데이터베이스 오류: {str(db_error)}")
            raise HTTPException(
                status_code=500,
                detail=f"관리자 계정 생성 중 오류가 발생했습니다: {str(db_error)}",
            )

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"예상치 못한 오류: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"서버 오류가 발생했습니다: {str(e)}"
        )
