from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import prices, indicator_router

app = FastAPI(title="BitNow API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 운영 환경에서는 구체적인 도메인 지정 필요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(prices.router)
app.include_router(indicator_router.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", 
        host="0.0.0.0",  # 모든 네트워크 인터페이스에서 접근 허용
        port=8000,
        reload=True
    )
