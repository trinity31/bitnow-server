# 비어있어도 됩니다
import os
from dotenv import load_dotenv

load_dotenv()

# Exchange Rate Constants
DEFAULT_USD_KRW_RATE = 1450.0
CACHE_DURATION_HOURS = 1

# Exchange Rate API URLs
EXCHANGE_RATE_API_URL = "https://open.er-api.com/v6/latest/USD"
ALPHA_VANTAGE_URL = "https://www.alphavantage.co/query"

# RSI 관련 상수
DEFAULT_RSI_LENGTH = 14
DEFAULT_RSI_INTERVAL = "minute15"
DEFAULT_SYMBOL = "BTC"

# RSI Intervals (Taapi.io format)
RSI_INTERVALS = {
    "15m": "15m",  # 15분
    "1h": "1h",  # 1시간
    "4h": "4h",  # 4시간
    "1d": "1d",  # 1일
}

# API 엔드포인트
COINMARKETCAP_API_URL = "https://pro-api.coinmarketcap.com/v1"
GLASSNODE_API_URL = "https://api.glassnode.com/v1"

# Mock 데이터 (실제 API 연동 전까지 사용)
MOCK_DOMINANCE = 50
MOCK_MVRV = 2.88

# Binance API URL
BINANCE_API_URL = "https://api.binance.com/api/v3"

TAAPI_URL = "https://api.taapi.io"

# WebSocket URLs
UPBIT_WS_URL = "wss://api.upbit.com/websocket/v1"
BINANCE_WS_URL = "wss://stream.binance.com:9443/ws/btcusdt@trade"

# WebSocket Constants
DEFAULT_PING_INTERVAL = 30  # 30초마다 ping
MAX_RECONNECT_ATTEMPTS = 5
RECONNECT_DELAY = 5  # 5초 후 재접속

# FCM 설정
FCM_SERVER_KEY = os.getenv("FCM_SERVER_KEY")

# 알림 생성 대량 처리 임계치
BATCH_CREATE_THRESHOLD = 1

# 크레딧 관련 상수
INITIAL_CREDIT_AMOUNT = 10  # 신규 사용자 초기 크레딧
CREDIT_PER_AD_VIEW = 10  # 광고 시청당 적립 크레딧
MIN_CREDIT_FOR_ALERT = 1  # 알림 발송에 필요한 최소 크레딧

# 공포/탐욕 지수 관련 상수
FEAR_GREED_API_URL = "https://api.alternative.me/fng/"
MOCK_FEAR_GREED_INDEX = 50

# 서버 설정 관련 상수
DEFAULT_HOST = "0.0.0.0"  # 모든 네트워크 인터페이스에서 접근 허용
DEFAULT_PORT = 8000  # 기본 포트

# API 관련 상수
API_TITLE = "BitNow API"
API_DESCRIPTION = "실시간 암호화폐 가격 및 기술적 지표 제공 API"
DEFAULT_API_VERSION = "1.0.0"
