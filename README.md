# 암호화폐 가격 조회 API

실시간으로 비트코인의 원화(KRW)와 달러(USD) 가격을 조회할 수 있는 FastAPI 기반 서비스입니다.

## 기능

- Upbit API를 통한 BTC-KRW 가격 조회
- Binance API를 통한 BTC-USD 가격 조회
- 비동기 처리를 통한 동시 가격 조회

## 시작하기

### 필수 요구사항

- Python 3.8 이상
- pip (파이썬 패키지 관리자)

### 설치 방법

#### 1. 저장소 클론

git clone [저장소 URL]
cd [프로젝트 디렉토리]

#### 2. 활성화

python -m venv venv

##### Windows

venv\Scripts\activate

##### macOS/Linux

source venv/bin/activate

#### 3. 설치

pip install -r requirements.txt

#### 4. 실행

uvicorn app.main:app --reload
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
