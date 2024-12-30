# 인증(Authentication) API 문서

사용자 등록 및 인증을 위한 API 엔드포인트들을 설명합니다.

## 회원가입

새로운 사용자 계정을 생성합니다.

### 요청

- Method: `POST`
- Endpoint: `/register`

### 요청 본문

```json
{
  "email": "user@example.com",
  "password": "your_password",
  "fcm_token": "firebase_cloud_messaging_token" // 선택사항
}
```

### 응답

```json
{
  "message": "User created successfully"
}
```

## 로그인

사용자 인증 및 JWT 토큰 발급.

### 요청

- Method: `POST`
- Endpoint: `/token`
- Content-Type: `application/x-www-form-urlencoded`

### 요청 파라미터

| 파라미터 | 타입   | 필수 | 설명          |
| -------- | ------ | ---- | ------------- |
| username | string | Y    | 사용자 이메일 |
| password | string | Y    | 비밀번호      |

### 응답

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

## 인증 사용 예시

1. 회원가입:

```bash
curl -X POST http://localhost:8000/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "your_password",
    "fcm_token": "optional_fcm_token"
  }'
```

2. 로그인:

```bash
curl -X POST http://localhost:8000/token \
  -d "username=user@example.com&password=your_password" \
  -H "Content-Type: application/x-www-form-urlencoded"
```

3. 보호된 API 호출 (예: 알림 조건 생성):

```bash
curl -X POST http://localhost:8000/alerts/condition \
  -H "Authorization: Bearer {your_access_token}" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "price",
    "symbol": "BTC",
    "threshold": 30000000,
    "direction": "above"
  }'
```

## 에러 응답

### 400 Bad Request

```json
{
  "detail": "Email already registered"
}
```

### 401 Unauthorized

```json
{
  "detail": "Incorrect email or password"
}
```

### 401 Invalid Token

```json
{
  "detail": "Could not validate credentials"
}
```

## 보안 참고사항

- 비밀번호는 bcrypt로 해시되어 저장됩니다
- JWT 토큰은 24시간 동안 유효합니다
- 모든 알림 관련 API는 유효한 JWT 토큰이 필요합니다
