#!/bin/bash

# AWS RDS → Railway 완전 마이그레이션 스크립트
# 사용법: RAILWAY_DATABASE_URL="postgresql://..." ./scripts/migrate_to_railway.sh

set -e

echo "🚀 AWS RDS → Railway 마이그레이션을 시작합니다..."

# Railway 연결 정보 확인
if [ -z "$RAILWAY_DATABASE_URL" ]; then
    echo "❌ RAILWAY_DATABASE_URL 환경 변수가 설정되지 않았습니다."
    echo "Railway PostgreSQL 연결 URL을 설정해주세요:"
    echo "export RAILWAY_DATABASE_URL='postgresql://username:password@host:port/database'"
    exit 1
fi

# 1. AWS RDS 백업
echo "📦 1단계: AWS RDS 백업..."
./scripts/backup_aws_rds.sh

# 최신 백업 파일 찾기
LATEST_BACKUP=$(ls -t backups/bitnow_backup_*.sql | head -n1)
echo "📁 사용할 백업 파일: $LATEST_BACKUP"

# 2. Railway로 복원
echo "🔄 2단계: Railway로 복원..."
RAILWAY_DATABASE_URL="$RAILWAY_DATABASE_URL" ./scripts/restore_to_railway.sh "$LATEST_BACKUP"

echo "✅ 마이그레이션 완료!"
echo ""
echo "🔧 다음 단계:"
echo "1. Railway에서 새 DATABASE_URL 복사"
echo "2. .env 파일의 PROD_DATABASE_URL 업데이트"
echo "3. 애플리케이션 재배포"
echo "4. 마이그레이션 검증"