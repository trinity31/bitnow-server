# BitNow Server

실시간 암호화폐 가격 및 기술적 지표 제공 서버

## 주요 기능

1. 실시간 가격 정보

   - 업비트 BTC/KRW
   - 바이낸스 BTC/USDT
   - 실시간 김치프리미엄 계산

2. 기술적 지표

   - RSI (15분, 1시간, 4시간, 1일)
   - 비트코인 도미넌스
   - MVRV (Market Value to Realized Value)

3. 실시간 알림 기능
   - 가격 알림 (상승/하락)
   - RSI 알림
   - 김치프리미엄 알림
   - FCM 푸시 알림 지원

## 기술 스택

- FastAPI
- WebSocket
- SQLAlchemy (SQLite)
- Firebase Cloud Messaging (FCM)

## 설치 및 실행

1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

2. 환경변수 설정 (.env 파일)

```env
# Exchange Rate API
ALPHA_VANTAGE_API_KEY=your_key_here

# Firebase
FCM_SERVER_KEY=your_fcm_server_key_here

# Database
DATABASE_URL="sqlite+aiosqlite:///./bitnow.db"
```

3. 서버 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API 엔드포인트

### WebSocket

- `ws://localhost:8000/ws/price`
  - 실시간 가격, RSI, 김치프리미엄 등 데이터 스트리밍

### REST API

- `GET /indicators/rsi/{symbol}`
  - RSI 값 조회
- `GET /indicators/dominance`
  - 비트코인 도미넌스 조회
- `GET /indicators/mvrv`
  - MVRV 비율 조회
- `POST /alerts/condition`
  - 알림 조건 생성
- `GET /alerts`
  - 활성화된 알림 조건 조회
- `POST /register`
  - 새로운 사용자 등록
- `POST /token`
  - 로그인 및 JWT 토큰 발급

### 터미널에서 웹소켓 연결 테스트

```bash
websocat ws://localhost:8000/ws/price
```

## 데이터 구조

### WebSocket 메시지 예시

```json
{
  "krw": 142171000.0,
  "usd": 94531.85,
  "timestamp": "2024-03-20T10:52:42.042814",
  "kimchi_premium": 2.34,
  "change_24h": {
    "krw": 5.23,
    "usd": 5.12
  },
  "rsi": {
    "15m": 65.42,
    "1h": 58.31,
    "4h": 62.15,
    "1d": 70.25
  },
  "mvrv": 2.88,
  "dominance": 52.31
}
```

### 알림 조건 생성 예시

```json
{
  "type": "price",
  "symbol": "BTC",
  "threshold": 30000000,
  "direction": "above"
}
```

## 업데이트 주기

- 가격 데이터: 실시간 (WebSocket)
- 브로드캐스트: 1초
- RSI: 각 간격별 (15분, 1시간, 4시간, 1일)
- 도미넌스: 1시간
- MVRV: 1시간
- 24시간 변동률: 1분

## 개발 환경 설정

1. VSCode 확장 프로그램

   - Python
   - Pylance
   - Black Formatter

2. 코드 포맷팅

```bash
black app/
```

## 라이센스

MIT License
