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
