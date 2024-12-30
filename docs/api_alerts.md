# 알림(Alerts) API 문서

사용자별 알림 조건을 관리하기 위한 API 엔드포인트들을 설명합니다.

## 1. 알림 조건 생성

새로운 알림 조건을 등록합니다.

### 요청

- Method: `POST`
- URL: `/alerts/condition`
- Headers:
  - Authorization: `Bearer {access_token}`
- Content-Type: `application/json`

### 요청 본문

```json
{
  "type": "price", // price, rsi, kimchi_premium, dominance, mvrv
  "symbol": "BTC", // 현재는 BTC만 지원
  "threshold": 30000000, // 임계값
  "direction": "above", // above, below
  "interval": "1h", // RSI용 (15m, 1h, 4h, 1d), RSI 타입일 때만 필요
  "currency": "KRW"
}
```

### 응답

- Status: 200 OK

```json
{
  "id": 1,
  "type": "price",
  "symbol": "BTC",
  "threshold": 30000000,
  "direction": "above",
  "interval": null,
  "currency": "KRW",
  "is_active": true,
  "created_at": "2024-03-21T10:00:00.000Z"
}
```

## 2. 알림 조건 목록 조회

사용자의 활성화된 알림 조건 목록을 조회합니다.

### 요청

- Method: `GET`
- URL: `/alerts`
- Headers:
  - Authorization: `Bearer {access_token}`

### 응답

- Status: 200 OK

```json
[
  {
    "id": 1,
    "type": "price",
    "symbol": "BTC",
    "threshold": 30000000,
    "direction": "above",
    "interval": null,
    "is_active": true,
    "created_at": "2024-03-21T10:00:00.000Z",
    "triggered_at": "2024-03-21T11:00:00.000Z"
  }
]
```

## 3. 알림 조건 삭제

특정 알림 조건을 삭제합니다.

### 요청

- Method: `DELETE`
- URL: `/alerts/{alert_id}`
- Headers:
  - Authorization: `Bearer {access_token}`

### 응답

- Status: 200 OK

```json
{
  "message": "Alert condition deleted successfully"
}
```

## 알림 타입별 설정 가이드

1. 가격 알림 (원화)

```json
{
  "type": "price",
  "symbol": "BTC",
  "threshold": 30000000, // 원화 가격
  "direction": "above", // 가격이 30,000,000원 이상일 때 알림
  "currency": "KRW" // 기본값
}
```

또는 달러 가격:

```json
{
  "type": "price",
  "symbol": "BTC",
  "threshold": 20000, // 달러 가격
  "direction": "below", // 가격이 $20,000 이하일 때 알림
  "currency": "USD"
}
```

2. RSI 알림

```json
{
  "type": "rsi",
  "symbol": "BTC",
  "threshold": 70, // RSI 값 (0-100)
  "direction": "above", // RSI가 70 이상일 때 알림
  "interval": "1h" // 15m, 1h, 4h, 1d 중 선택
}
```

3. 김치프리미엄 알림

```json
{
  "type": "kimchi_premium",
  "symbol": "BTC",
  "threshold": 5.0, // 프리미엄 %
  "direction": "above" // 프리미엄이 5% 이상일 때 알림
}
```

4. 도미넌스 알림

```json
{
  "type": "dominance",
  "symbol": "BTC",
  "threshold": 50.0, // 도미넌스 %
  "direction": "below" // 도미넌스가 50% 이하일 때 알림
}
```

5. MVRV 알림

```json
{
  "type": "mvrv",
  "symbol": "BTC",
  "threshold": 3.0, // MVRV 비율
  "direction": "above" // MVRV가 3.0 이상일 때 알림
}
```

## 에러 응답

- Status: 400 Bad Request

```json
{
  "code": "INVALID_INPUT",
  "message": "잘못된 입력입니다"
}
```

- Status: 401 Unauthorized

```json
{
  "code": "TOKEN_EXPIRED",
  "message": "토큰이 만료되었습니다. 다시 로그인해주세요"
}
```

- Status: 404 Not Found

```json
{
  "code": "ALERT_NOT_FOUND",
  "message": "알림 조건을 찾을 수 없습니다"
}
```

## 참고사항

1. 알림 발생 주기

   - 동일한 조건의 알림은 최소 5분 간격으로 발생
   - 알림 발생 후 조건이 해제되었다가 다시 만족해야 재발생

2. 알림 전달 방식

   - FCM(Firebase Cloud Messaging)을 통한 푸시 알림
   - 회원가입 시 등록한 FCM 토큰으로 전송

3. 제한사항
   - 사용자당 최대 10개의 활성 알림 조건 설정 가능
   - 알림 조건 생성/삭제는 로그인 필수
