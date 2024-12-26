[프로젝트 개요]  
- FastAPI 백엔드로 원화 시세(Pyupbit), 달러 시세(Binance)를 동시에 수집하는 서비스의 초기 버전을 구현하려고 합니다.
- Day 1 단계에서는 다음 작업을 목표로 합니다.

[Day 1 목표]  
1) FastAPI 프로젝트 구조 설계  
   - 프로젝트 폴더 구성(`app/`, `app/main.py`, `app/routers/`, `app/services/` 등),  
   - 가상환경 설정(필요 시), 의존성 패키지 설치(`fastapi`, `uvicorn`, `requests`, `pydantic` 등).  

2) Pyupbit & Binance API 연결 테스트  
   - Pyupbit로 현재 BTC 원화 시세 가져오기  
   - Binance로 현재 BTC 달러 시세 가져오기  
   - 간단한 함수/엔드포인트(`GET /prices`)로 가격 JSON 응답 리턴  
     (예: `{ "btc_krw": 34000000, "btc_usd": 27000 }` 형태)

3) Flutter UI에 표시할 준비  
   - 일단 Flutter 관련 부분은 이번에 직접 코드 생성은 필요 없지만,  
     FastAPI로부터 JSON 형태로 받아오는 구조만 테스트.
   - 추가로 Flutter 쪽에서 받기 편하도록 JSON 스키마(응답 형식) 간략 주석 작성.

[구현 상세 요구사항]  
1. FastAPI 서버 실행 시, `/prices` 엔드포인트를 통해 원화/달러 시세를 JSON으로 응답  
2. Pyupbit, Binance API로 가격을 가져오는 로직은 `services/price_service.py` 같은 모듈에 작성  
3. main.py 혹은 routers 디렉토리에 `prices_router.py`를 두고, 라우트 등록  
4. 코드 내에 주석으로 간단하게 각 부분 설명  

[결과물]  
1) FastAPI 프로젝트 디렉토리/코드 샘플  
2) `GET /prices` 호출 시 응답 예시  
3) 로컬에서 테스트하는 방법(예: `uvicorn app.main:app --reload`)  

위 요구사항을 바탕으로 코드를 생성해 주세요.  
가능하면 코드 전체(폴더 구조, *.py 파일 내용)를 한 번에 출력해 주시고,  
부분별로 주석이나 간단한 설명을 첨부해 주시면 좋겠습니다.
