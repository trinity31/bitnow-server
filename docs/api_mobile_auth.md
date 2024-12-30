# 모바일 인증 API 문서

모바일 앱에서 사용할 수 있는 인증 관련 API 엔드포인트들을 설명합니다.

## 1. 회원가입

새로운 사용자 계정을 생성합니다.

### 요청

- Method: `POST`
- URL: `/auth/register`
- Content-Type: `application/json`

### 요청 본문

```json
{
  "email": "user@example.com",
  "password": "password123",
  "fcm_token": "firebase_cloud_messaging_token" // 선택사항
}
```

### 응답

- Status: 200 OK

```json
{
  "message": "User created successfully"
}
```

### 에러

- Status: 400 Bad Request

```json
{
  "code": "EMAIL_EXISTS",
  "message": "이미 등록된 이메일입니다"
}
```

```json
{
  "code": "INVALID_INPUT",
  "message": "잘못된 입력입니다"
}
```

- Status: 401 Unauthorized

```json
{
  "code": "INVALID_CREDENTIALS",
  "message": "이메일 또는 비밀번호가 올바르지 않습니다"
}
```

- Status: 500 Internal Server Error

```json
{
  "code": "SERVER_ERROR",
  "message": "서버 오류가 발생했습니다"
}
```

## 2. 로그인

사용자 인증 및 JWT 토큰 발급.

### 요청

- Method: `POST`
- URL: `/auth/login/json`
- Content-Type: `application/json`

### 요청 본문

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

### 응답

- Status: 200 OK

```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### 에러

- Status: 401 Unauthorized

```json
{
  "detail": "Incorrect email or password"
}
```

## 3. 로그아웃

현재 로그인된 사용자의 로그아웃을 처리합니다.

### 요청

- Method: `POST`
- URL: `/auth/logout`
- Headers:
  - Authorization: `Bearer {access_token}`

### 응답

- Status: 200 OK

```json
{
  "message": "Successfully logged out"
}
```

### 에러

- Status: 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

## 4. 회원 탈퇴

현재 로그인된 사용자의 계정을 삭제합니다.

### 요청

- Method: `DELETE`
- URL: `/auth/me`
- Headers:
  - Authorization: `Bearer {access_token}`

### 응답

- Status: 200 OK

```json
{
  "message": "User account deleted successfully"
}
```

### 에러

- Status: 401 Unauthorized

```json
{
  "detail": "Could not validate credentials"
}
```

## 인증 헤더 사용 방법

로그인 후 받은 access_token을 모든 보호된 API 요청의 헤더에 포함해야 합니다:

```
Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGc...
```

## 참고사항

1. 비밀번호 요구사항

   - 최소 8자 이상
   - 최대 길이 제한 없음

2. 이메일 형식

   - 표준 이메일 형식 (예: user@example.com)
   - 대소문자 구분 없음

3. FCM 토큰

   - 회원가입 시 선택적으로 제공
   - 푸시 알림 수신을 위해 필요

4. 토큰 관리

   - JWT 토큰의 유효기간은 30일
   - 로그아웃 시 클라이언트에서 토큰 삭제 필요
   - 토큰 만료 시 재로그인 필요

5. 에러 처리
   - 모든 에러 응답은 `detail` 필드에 에러 메시지 포함
   - HTTP 상태 코드로 에러 종류 구분

### 토큰 관련 에러

- Status: 401 Unauthorized

1. 토큰 만료

```json
{
  "code": "TOKEN_EXPIRED",
  "message": "토큰이 만료되었습니다. 다시 로그인해주세요"
}
```

2. 유효하지 않은 토큰

```json
{
  "code": "INVALID_TOKEN",
  "message": "유효하지 않은 토큰입니다"
}
```

3. 사용자 없음

```json
{
  "code": "USER_NOT_FOUND",
  "message": "사용자를 찾을 수 없습니다"
}
```

클라이언트 구현 시:

1. 모든 API 호출에서 401 에러 확인
2. 특히 `TOKEN_EXPIRED` 코드를 받으면 로그인 화면으로 이동
3. 다른 401 에러는 적절한 에러 메시지 표시

## FCM 토큰 업데이트

### 요청

- Method: `PUT`
- URL: `/auth/fcm-token`
- Headers:
  - Authorization: `Bearer {access_token}`
- Content-Type: `application/json`

### 요청 본문

```json
{
  "fcm_token": "new_fcm_token_here"
}
```

### 응답

- Status: 200 OK

```json
{
  "message": "FCM token updated successfully"
}
```

### 에러

- Status: 500 Internal Server Error

```json
{
  "code": "UPDATE_FAILED",
  "message": "FCM 토큰 업데이트에 실패했습니다"
}
```

클라이언트 구현 시:

1. 앱 시작할 때마다 FCM 토큰 확인
2. 토큰이 변경되었다면 서버에 업데이트 요청
3. 토큰 업데이트 실패 시 적절한 에러 처리
