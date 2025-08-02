#!/bin/bash

# Railway PostgreSQL로 데이터 복원 스크립트
# 사용법: ./scripts/restore_to_railway.sh <backup_file>

set -e

if [ $# -eq 0 ]; then
    echo "❌ 백업 파일을 지정해주세요."
    echo "사용법: $0 <backup_file>"
    echo "예시: $0 backups/bitnow_backup_20240102_123456.sql"
    exit 1
fi

BACKUP_FILE=$1

if [ ! -f "$BACKUP_FILE" ]; then
    echo "❌ 백업 파일을 찾을 수 없습니다: $BACKUP_FILE"
    exit 1
fi

echo "🚀 Railway PostgreSQL로 복원을 시작합니다..."

# Railway 연결 정보 (환경 변수에서 가져오기)
# Railway에서 제공하는 DATABASE_URL 사용
if [ -z "$RAILWAY_DATABASE_URL" ]; then
    echo "❌ RAILWAY_DATABASE_URL 환경 변수가 설정되지 않았습니다."
    echo "Railway PostgreSQL 연결 URL을 RAILWAY_DATABASE_URL 환경 변수에 설정해주세요."
    echo "예시: export RAILWAY_DATABASE_URL='postgresql://username:password@host:port/database'"
    exit 1
fi

echo "📦 데이터베이스 복원 중..."
echo "백업 파일: $BACKUP_FILE"
echo "대상 DB: Railway PostgreSQL"

# PostgreSQL 16 psql을 사용하여 복원
PSQL_PATH="/opt/homebrew/opt/postgresql@16/bin/psql"
$PSQL_PATH "$RAILWAY_DATABASE_URL" -f "$BACKUP_FILE" -v ON_ERROR_STOP=1

echo "✅ 복원 완료!"

echo "🔍 복원 결과 확인:"
$PSQL_PATH "$RAILWAY_DATABASE_URL" -c "\dt" -c "SELECT schemaname,tablename,tableowner FROM pg_tables WHERE schemaname='public';"