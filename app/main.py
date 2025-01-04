from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.routers import prices, indicator_router, ws_router, auth_router, alerts_router
from app.services.stream_service import stream_service
from app.services.push_service import push_service
import asyncio
import logging
from app.database import engine
from app.models import Base

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BitNow API",
    description="실시간 암호화폐 가격 및 기술적 지표 제공 API",
    version="1.0.0",
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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=400,
        content={"code": "INVALID_INPUT", "message": "잘못된 입력입니다"},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",  # 모든 네트워크 인터페이스에서 접근 허용
        port=8000,
        reload=True,
    )
