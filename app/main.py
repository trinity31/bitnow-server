from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routers import (
    prices,
    indicator_router,
    ws_router,
    auth_router,
    alerts_router,
    credit_router,
)
from app.services.stream_service import stream_service
from app.services.push_service import push_service
import asyncio
import logging
from app.database import engine
from app.models import Base
from contextlib import asynccontextmanager
from app.constants import API_TITLE, API_DESCRIPTION, DEFAULT_API_VERSION
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    asyncio.create_task(stream_service.start())
    yield
    # Shutdown
    await stream_service.stop()


app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=DEFAULT_API_VERSION,
    lifespan=lifespan,
    # OpenAPI에 보안 스키마 추가
    openapi_tags=[
        {"name": "auth", "description": "인증 관련 API"},
        {"name": "alerts", "description": "알림 관련 API"},
        {"name": "indicators", "description": "지표 관련 API"},
    ],
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(
    auth_router.router,
    tags=["auth"],
)
app.include_router(
    prices.router,
    tags=["prices"],
)
app.include_router(
    indicator_router.router,
    tags=["indicators"],
)
app.include_router(
    ws_router.router,
    tags=["websocket"],
)
app.include_router(
    alerts_router.router,
    tags=["alerts"],
)
app.include_router(credit_router.router)


@app.on_event("startup")
async def startup_event():
    """서버 시작 시 WebSocket 스트리밍과 푸시 서비스 시작"""
    asyncio.create_task(stream_service.start())
    # push_service는 __init__에서 자동으로 초기화되지만,
    # 초기화 상태를 확인하고 로그를 남깁니다.
    if not push_service.initialized:
        logger.error("Push service failed to initialize")
    else:
        logger.info("Push service initialized successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 WebSocket 스트리밍 중지"""
    await stream_service.stop()


@app.on_event("startup")
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 초기 크레딧 생성
    from app.migrations.create_initial_credits import create_initial_credits

    await create_initial_credits()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_INPUT", "message": "잘못된 입력입니다"},
    )


@app.get("/health")
async def health_check():
    """서비스 헬스 체크 엔드포인트"""
    return {"status": "OK"}


if __name__ == "__main__":
    import uvicorn
    import os
    from app.constants import DEFAULT_HOST, DEFAULT_PORT

    port = int(os.environ.get("PORT", DEFAULT_PORT))

    uvicorn.run(
        "app.main:app",
        host=DEFAULT_HOST,
        port=port,
        reload=True,
    )
