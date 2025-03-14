# Railway 배포 가이드

이 문서는 BitNow 서버를 Railway 플랫폼에 배포하는 방법을 설명합니다.

## 사전 준비

1. [Railway 계정](https://railway.app/) 생성
2. Railway CLI 설치 (선택 사항)
   ```bash
   npm i -g @railway/cli
   ```

## 배포 방법

### 1. Railway 대시보드에서 배포

1. [Railway 대시보드](https://railway.app/dashboard)에 로그인합니다.
2. "New Project" 버튼을 클릭합니다.
3. "Deploy from GitHub repo" 옵션을 선택합니다.
4. BitNow 서버 저장소를 선택합니다.
5. 배포가 시작되면 Railway가 자동으로 Dockerfile을 감지하고 빌드합니다.

### 2. 환경 변수 설정

Railway 대시보드에서 다음 환경 변수를 설정해야 합니다:

- `ENVIRONMENT`: `prod`로 설정
- `EXCHANGE_API_KEY`: 거래소 API 키
- `COINMARKETCAP_API_KEY`: CoinMarketCap API 키
- `TAAPI_SECRET`: TaAPI 시크릿 키
- `ALPHA_VANTAGE_API_KEY`: Alpha Vantage API 키
- `ADMIN_SECRET_KEY`: 관리자 시크릿 키
- `SLACK_WEBHOOK_URL`: Slack 웹훅 URL
- `OPENAI_API_KEY`: OpenAI API 키
- `PROD_DATABASE_URL`: AWS RDS 데이터베이스 URL (기존 RDS 사용 시)

### 3. Firebase 인증 정보 설정

Firebase 인증 정보를 Railway에 설정하는 방법은 두 가지가 있습니다:

#### 방법 1: 환경 변수로 설정 (권장)

1. `firebase-adminsdk.json` 파일의 내용 전체를 복사합니다.
2. Railway 대시보드에서 "Variables" 탭을 선택합니다.
3. `FIREBASE_CREDENTIALS_JSON` 환경 변수를 추가하고 값으로 JSON 내용을 붙여넣습니다.

예시:

```
FIREBASE_CREDENTIALS_JSON={"type":"service_account","project_id":"bitnow-2bb9f","private_key_id":"662846edae96f08e6b4817e1a7905217350a6628","private_key":"-----BEGIN PRIVATE KEY-----\n...-----END PRIVATE KEY-----\n",...}
```

이 방법은 파일을 업로드할 필요 없이 환경 변수만으로 Firebase 인증을 설정할 수 있어 더 안전하고 편리합니다.

#### 방법 2: 파일 업로드

1. Railway 대시보드에서 "Files" 탭을 선택합니다.
2. "Upload" 버튼을 클릭하고 `firebase-adminsdk.json` 파일을 업로드합니다.
3. `FIREBASE_CREDENTIALS` 환경 변수를 추가하고 값으로 파일 경로를 설정합니다 (예: `/app/firebase-adminsdk.json`).

### 4. 데이터베이스 설정

#### 옵션 1: 기존 AWS RDS 계속 사용 (권장)

기존 AWS RDS 데이터베이스를 계속 사용하려면:

1. Railway 대시보드에서 "Variables" 탭을 선택합니다.
2. `PROD_DATABASE_URL` 환경 변수를 추가하고 기존 AWS RDS 연결 문자열을 설정합니다.
   ```
   postgresql+asyncpg://master:5631athp@bitnow-db-instance.c5k2y4ksghoa.ap-northeast-2.rds.amazonaws.com:5432/bitnow
   ```
3. `USE_RAILWAY_DB` 환경 변수를 `false`로 설정합니다.

이 방법을 사용하면 기존 데이터를 그대로 유지하면서 애플리케이션을 Railway로 이전할 수 있습니다.

#### 옵션 2: Railway PostgreSQL 데이터베이스 사용

Railway에서 제공하는 PostgreSQL 데이터베이스를 사용하려면:

1. Railway 대시보드에서 프로젝트를 선택합니다.
2. "New" 버튼을 클릭하고 "Database" > "PostgreSQL"을 선택합니다.
3. Railway가 자동으로 `DATABASE_URL` 환경 변수를 설정합니다.
4. `USE_RAILWAY_DB` 환경 변수를 `true`로 설정합니다.

이 방법을 사용하면 새로운 데이터베이스에서 시작하므로 마이그레이션을 실행하여 스키마를 생성해야 합니다.

### 5. 마이그레이션 실행 (Railway 데이터베이스 사용 시)

Railway 데이터베이스를 사용하는 경우 마이그레이션을 실행하여 스키마를 생성해야 합니다:

1. Railway 대시보드에서 "Connect" 버튼을 클릭합니다.
2. "Shell" 옵션을 선택합니다.
3. 다음 명령어를 실행합니다:
   ```bash
   alembic upgrade head
   ```

## 모니터링 및 로그

- Railway 대시보드에서 "Deployments" 탭을 선택하여 배포 상태를 확인할 수 있습니다.
- "Logs" 탭에서 애플리케이션 로그를 확인할 수 있습니다.

## 문제 해결

- 배포 실패 시 Railway 대시보드의 "Logs" 탭에서 오류 메시지를 확인하세요.
- 데이터베이스 연결 문제가 발생하면 `PROD_DATABASE_URL` 또는 `DATABASE_URL` 환경 변수가 올바르게 설정되었는지 확인하세요.
- Firebase 인증 문제가 발생하면 `FIREBASE_CREDENTIALS_JSON` 또는 `FIREBASE_CREDENTIALS` 환경 변수가 올바르게 설정되었는지 확인하세요.

## 참고 사항

- Railway는 기본적으로 HTTPS를 제공합니다.
- Railway는 자동으로 `PORT` 환경 변수를 설정합니다.
- Railway는 자동으로 `DATABASE_URL` 환경 변수를 설정합니다 (PostgreSQL 데이터베이스를 추가한 경우).
- Railway는 자동으로 CI/CD를 제공하므로 GitHub 저장소에 변경 사항을 푸시하면 자동으로 배포됩니다.
