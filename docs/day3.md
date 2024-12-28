[프로젝트 개요]
- 이미 Day 2까지 MVRV 등 여러 지표를 구현했습니다.
- Day 3에는 REST 방식이 아닌, “업비트, 바이낸스 WebSocket”을 통해 비트코인 시세를 실시간으로 스트리밍 받아서, 내부적으로 저장/가공 후, 우리 서비스의 클라이언트에게도 WebSocket으로 전달하려고 합니다.

[Day 3 상세 요구사항]

1) 업비트, 바이낸스 WebSocket 연결
   - 업비트 WebSocket: wss://api.upbit.com/websocket/v1
     - 예: 특정 종목(BTC-KRW) 체결/호가/틱 데이터 스트리밍
   - 바이낸스 WebSocket: wss://stream.binance.com:9443/ws/btcusdt@trade
     - BTCUSDT 체결/틱 데이터 스트리밍
   - 이 두 WebSocket 연결을 각각 비동기로 열고, 데이터가 오면 파싱(가격, 거래량, 타임스탬프 등)을 수행

2) 서버 내부 처리
   - 받은 실시간 시세 데이터를 “메모리 캐시” 또는 “전역 변수”로 저장
   - 필요한 경우, 김치 프리미엄 계산까지 실시간 업데이트(옵션)

3) 웹소켓 엔드포인트 (서버 -> 클라이언트)
   - FastAPI에서 `/ws/price` 등 WebSocket 라우트를 열어둠
   - 서버 내부에서 업비트·바이낸스 WebSocket으로 받은 최신 시세를 클라이언트에 **broadcast**:
     - 모든 연결된 클라이언트에게 `{ "krwPrice": ..., "usdPrice": ..., "timestamp": ... }`를 전송
   - 여러 클라이언트 관리(set or list)에 대한 예시 필요

4) 코드 구조
   - 예: `services/stream_service.py` 에서 “업비트, 바이낸스 WebSocket” 연결 로직
   - `routers/ws_router.py` 에서 “/ws/price” 라우트 + broadcast
   - asyncio 기반으로 run_forever하거나, FastAPI startup 이벤트에서 Task로 실행
   - 주석으로 각 부분 역할 설명

5) 최종 결과
   - 서버 실행 시, 즉시 업비트·바이낸스 WebSocket 연결
   - 실시간 가격(1초보다 더 자주, 체결될 때마다) 데이터가 들어옴
   - `/ws/price` 에 클라이언트가 WebSocket 연결하면, 실시간 시세를 push로 전달받음

[추가 요청사항]
- 전체 코드 예시(파일 구조, main.py, stream_service.py, ws_router.py, requirements.txt 등)를 생성해주세요.
- 업비트, 바이낸스 WebSocket 예제 코드(구독 메시지 전송, JSON 파싱 방식 등)도 보여주세요.
- 실제 테스트 방법(“websocat ws://localhost:8000/ws/price” 등) 제시해 주시면 좋습니다.

위 요구사항대로 코드를 작성해 주세요.
