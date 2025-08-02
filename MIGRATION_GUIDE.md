# AWS RDS → Railway 데이터베이스 마이그레이션 가이드

## 📋 마이그레이션 개요

현재 AWS RDS PostgreSQL에서 Railway PostgreSQL로 데이터베이스를 이전하는 가이드입니다.

## 🚀 마이그레이션 단계

### 1. Railway 데이터베이스 서비스 생성

1. [Railway 콘솔](https://railway.app)에 로그인
2. **New Project** → **Add a service** → **Database** → **PostgreSQL** 선택
3. 생성된 PostgreSQL 서비스에서 **Variables** 탭에서 `DATABASE_URL` 복사

### 2. 필요한 도구 설치

```bash
# PostgreSQL 클라이언트 도구 설치 (macOS)
brew install postgresql

# 또는 Ubuntu/Debian
sudo apt-get install postgresql-client
```

### 3. 환경 변수 설정

```bash
# Railway 데이터베이스 URL 설정
export RAILWAY_DATABASE_URL="postgresql://postgres:ttdLgFiMFlESeYIveBHARPozHjyORoBA@postgres.railway.internal:5432/railway"
```

### 4. 마이그레이션 실행

#### 방법 1: 자동 마이그레이션 (권장)

```bash
# 전체 마이그레이션 자동 실행
RAILWAY_DATABASE_URL="postgresql://postgres:ttdLgFiMFlESeYIveBHARPozHjyORoBA@postgres.railway.internal:5432/railway" ./scripts/migrate_to_railway.sh
```

#### 방법 2: 단계별 수동 실행

```bash
# 1단계: AWS RDS 백업
./scripts/backup_aws_rds.sh

# 2단계: Railway로 복원
RAILWAY_DATABASE_URL="your_railway_url" ./scripts/restore_to_railway.sh backups/bitnow_backup_YYYYMMDD_HHMMSS.sql
```

### 5. 환경 변수 업데이트

`.env` 파일의 `PROD_DATABASE_URL`을 Railway URL로 변경:

```env
# 기존 AWS RDS
# PROD_DATABASE_URL="postgresql+asyncpg://master:5631athp@bitnow-db-instance.c5k2y4ksghoa.ap-northeast-2.rds.amazonaws.com:5432/bitnow"

# 새로운 Railway DB
PROD_DATABASE_URL="postgresql+asyncpg://username:password@railway-host:port/database"
```

### 6. 마이그레이션 검증

```bash
# Railway URL을 환경 변수로 설정
export RAILWAY_DATABASE_URL="your_railway_url"

# 검증 스크립트 실행
python scripts/verify_migration.py
```

### 7. 애플리케이션 재배포

```bash
# Railway에 재배포
railway up

# 또는 로컬에서 테스트
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🔍 검증 체크리스트

- [ ] 모든 테이블이 정상적으로 마이그레이션됨
- [ ] 레코드 수가 일치함
- [ ] 애플리케이션이 정상 작동함
- [ ] WebSocket 연결이 정상적으로 작동함
- [ ] 알림 기능이 정상 작동함

## ⚠️ 주의사항

1. **백업 확인**: 마이그레이션 전 반드시 데이터 백업 확인
2. **다운타임**: 마이그레이션 과정에서 서비스 중단 시간 고려
3. **연결 정보**: Railway 연결 정보는 민감 정보이므로 안전하게 관리
4. **테스팅**: 프로덕션 적용 전 충분한 테스트 수행

## 🔧 문제해결

### 연결 오류
```bash
# Railway 데이터베이스 연결 테스트
psql "$RAILWAY_DATABASE_URL" -c "SELECT version();"
```

### 권한 오류
```bash
# 스크립트 실행 권한 부여
chmod +x scripts/*.sh
```

### 복원 오류
- 백업 파일 경로 확인
- Railway 데이터베이스 용량 확인
- 네트워크 연결 상태 확인

## 📞 지원

마이그레이션 과정에서 문제가 발생하면:
1. 로그 파일 확인
2. Railway 콘솔에서 데이터베이스 상태 확인
3. 백업 파일 무결성 검증