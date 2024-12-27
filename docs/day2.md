[프로젝트 개요]  
- Day 1에서 /prices 및 김치 프리미엄 관련 엔드포인트 구현을 완료했습니다.
- Day 2에서는 RSI, 비트코인 도미넌스(또는 알트코인 시즌 인덱스), MVRV 등 새로운 지표 계산·조회 기능을 추가하려고 합니다.

[Day 2 상세 요구사항]  

1) RSI 계산
   - 업비트(또는 바이낸스)에서 최근 캔들 데이터를 일정 개수(N) 수집  
   - TA-Lib, pandas_ta, 혹은 직접 구현으로 RSI 계산  
   - 새 엔드포인트 예: `GET /indicator/rsi`  
     - 응답 예시: `{ "rsi": 65.3 }`
     - 파라미터(`?symbol=BTC&interval=minute15&length=14`) 등으로 유연성 부여해도 좋음  

2) 비트코인 도미넌스 or 알트코인 시즌 인덱스  
   - CoinMarketCap, Blockchain Center 등에서 데이터 수집(REST API나 스크래핑)  
   - 새 엔드포인트 예: `GET /indicator/dominance` 또는 `GET /indicator/altseason`  
     - 응답 예시: `{ "dominance": 45.2 }` 혹은 `{ "altcoin_season_index": 72 }`  

3) MVRV  
   - Glassnode, CryptoQuant, Santiment 등 온체인 지표 API를 사용하거나, 임시 Mock 데이터로 구현  
   - 새 엔드포인트 예: `GET /indicator/mvrv`  
     - 응답 예시: `{ "mvrv": 1.2 }`  
   - 실제 API가 없다면, 우선 하드코딩으로 구조만 잡아두고, 값만 반환해도 됨

4) 코드 구조  
   - `services/indicator_service.py`(또는 비슷한 폴더)에서 RSI, 도미넌스, MVRV 로직 분리  
   - `routers/indicator_router.py`에서 `/indicator/rsi`, `/indicator/dominance`, `/indicator/mvrv` 라우트 정의  
   - 모듈화 & 주석 달기

5) 결과물  
   - 서버 실행 시,  
     - `GET /indicator/rsi` → `{ "rsi": ... }`  
     - `GET /indicator/dominance` → `{ "dominance": ... }`  
     - `GET /indicator/mvrv` → `{ "mvrv": ... }`  
   - Day 3에 알림 로직 등 확장 가능

[추가 요청사항]  
- API 호출 또는 스크래핑 예시(비트코인 도미넌스, 알트시즌, MVRV)가 없다면 Mock 함수로 대체하고 주석으로 “TODO” 명시  
- 실행/테스트 방법과 샘플 JSON 응답도 포함해 주세요.
- 코드 전체(파일 구조)와 주요 함수에 간단한 설명/주석을 달아 주세요.

위 요구사항에 맞춰 코드를 생성해 주세요.
