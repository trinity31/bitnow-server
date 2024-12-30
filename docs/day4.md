[프로젝트 개요]
- Day 3까지 업비트·바이낸스 WebSocket으로 실시간 시세를 받고, /ws/price로 클라이언트에 송출하는 구조를 완성했습니다.
- Day 4에서는 사용자가 설정한 조건(가격 돌파, RSI 임계값, 김치프리미엄 특정 % 등)이 발생했을 때
  푸시 알림(Push Notification)을 보낼 수 있도록 백엔드 로직과 DB 구조를 준비하려고 합니다.

[Day 4 상세 요구사항]

1) 사용자 알림 조건 저장 로직
   - DB는 Prisma ORM 사용하고 우선 sqlite 로 진행.
   - 사용자별(또는 전역)으로 “알림 조건”을 저장할 수 있는 API:
     - 예: `POST /alerts/condition`
       - Body: `{ "type": "price", "symbol": "BTC", "threshold": 30000000, "direction": "above" }`
       - 위 예시는 “BTC 가격이 3천만 원 이상이면 알림” 뜻
     - 응답: 저장된 알림 조건 ID

2) 이벤트 감시 & 알림 트리거
   - 이미 Day 3에서 1초 단위 또는 WebSocket 메시지 단위로 시세를 받고 있으므로,
     시세 수신 시 “check_alerts()” 같은 함수를 호출
   - 조건 만족 시, DB(또는 큐)에 “알림 요청” 생성
   - Day 4에서는 실제 푸시 발송까지 구현해도 좋지만, 우선 “알림이 트리거되었다”는 콘솔 로그 or 임시 목록에 기록
   - (선택) Firebase Cloud Messaging(FCM)이나 APNs, SNS 등 연동 시, 알림 토큰 관리 로직도 작성

3) 알림 발송 초안
   - (선택) 실제 푸시 발송을 원한다면, 예: “FCM 서버 키”를 사용해 HTTP POST
   - 예시:
     ```python
     def send_push_notification(token, title, body):
         # requests.post("https://fcm.googleapis.com/fcm/send", ...)
         # headers, json body를 설정
         # 주석으로 구체적인 스펙 적기
     ```
   - Day 4에서는 “기본 푸시 메시지” 정도만, 세부 설정(아이콘, 소리 등)은 Day 5에 다듬기

4) 코드 구조
   - `routers/alerts_router.py` → 알림 조건 생성/조회/삭제 API
   - `services/alert_service.py` → 시세 수신 시 조건 검사 + 알림 트리거
   - (선택) `services/push_service.py` → FCM 연동 로직
   - 주석으로 각 단계(조건 확인, 발송) 설명

5) 최종 결과
   - 서버 실행 후, 사용자가 `POST /alerts/condition` 로 특정 조건 등록
   - 시세가 해당 조건에 부합하면 “알림 트리거”가 발생 (Day 4는 콘솔 로그 or 임시 방식)
   - (선택) FCM 토큰을 저장해 놓았다면 실제 스마트폰 푸시 알림까지 전송
   - Day 5에서 알림 UI, 세부 설정, TTS 등 확장 예정

[추가 요청사항]
- 전체 코드 예시(파일 구조, alerts_router.py, alert_service.py, push_service.py 등)를 보여주세요.
- FCM 연동 예시(간단)나 토큰 관리 DB 구조(예: user_id, fcm_token)도 스케치해 주시면 좋습니다.
- 테스트 방법(“어떤 조건으로 어떻게 등록하고, 어떻게 확인하는지?”)도 안내해 주세요.

위 요구사항에 맞춰 코드를 생성해 주세요.
