# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 주요 명령어

### 개발 서버 실행
```bash
# 가상환경 활성화
source venv/bin/activate

# 개발 서버 실행 (리로드 모드)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 또는 Python으로 직접 실행
python -m app.main
```

### 코드 포맷팅
```bash
black app/
```

### 데이터베이스 마이그레이션
```bash
# 마이그레이션 생성
alembic revision --autogenerate -m "migration message"

# 마이그레이션 적용
alembic upgrade head
```

### 테스트
```bash
# WebSocket 연결 테스트
websocat ws://localhost:8000/ws/price
```

## 아키텍처 개요

### 핵심 기술 스택
- **FastAPI**: 비동기 웹 프레임워크
- **SQLAlchemy**: 비동기 ORM (SQLite/PostgreSQL)
- **WebSocket**: 실시간 데이터 스트리밍
- **Firebase**: 푸시 알림 서비스
- **Alembic**: 데이터베이스 마이그레이션

### 주요 서비스 구조

#### 1. StreamService (`app/services/stream_service.py`)
- 업비트, 바이낸스 WebSocket 연결 관리
- 실시간 가격 데이터 수집 및 클라이언트 브로드캐스트
- 김치프리미엄, RSI, 거래량 계산
- 자동 재연결 및 에러 핸들링

#### 2. 핵심 서비스들
- `alert_service.py`: 가격/지표 알림 관리
- `indicator_service.py`: RSI, MVRV, 도미넌스 계산
- `exchange_service.py`: 환율 정보 처리
- `push_service.py`: FCM 푸시 알림 발송
- `credit_service.py`: 사용자 크레딧 관리

#### 3. 데이터베이스 모델
- `User`: 사용자 정보, FCM 토큰, 언어 설정
- `Alert`: 가격/지표 알림 조건
- `Credit`: 사용자 크레딧 시스템
- `MVRVIndicator`, `FearGreedIndicator`: 기술적 지표 저장

### API 구조
- `/auth`: JWT 기반 인증
- `/alerts`: 알림 조건 CRUD
- `/indicators`: RSI, MVRV, 도미넌스 조회
- `/ws/price`: 실시간 가격 데이터 WebSocket
- `/credit`: 크레딧 관리

### 환경 설정
- `.env` 파일 필수: `ALPHA_VANTAGE_API_KEY`, `FCM_SERVER_KEY`, `DATABASE_URL`
- `ENVIRONMENT=prod` 시 PostgreSQL 사용
- Firebase Admin SDK 키 필요 (`firebase-adminsdk.json`)

### 특별한 기능들
- **김치프리미엄**: 업비트/바이낸스 가격 차이 실시간 계산
- **다국어 지원**: 한국어/영어 알림 메시지 (`app/constants/messages.py`)
- **크레딧 시스템**: 알림 설정 시 크레딧 소모
- **이동평균선 교차**: 골든크로스/데드크로스 감지

### 주의사항
- WebSocket 연결은 서버 시작 시 자동으로 초기화됨
- SQLAlchemy 로깅이 기본적으로 비활성화되어 있음
- CORS가 모든 출처에 대해 허용되어 있음 (프로덕션에서 수정 필요)
- 중복된 startup 이벤트 핸들러가 있어 정리가 필요할 수 있음