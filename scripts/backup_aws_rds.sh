#!/bin/bash

# AWS RDS 데이터베이스 백업 스크립트
# 사용법: ./scripts/backup_aws_rds.sh

set -e

echo "🚀 AWS RDS 백업을 시작합니다..."

# RDS 연결 정보
RDS_HOST="bitnow-db-instance.c5k2y4ksghoa.ap-northeast-2.rds.amazonaws.com"
RDS_PORT="5432"
RDS_DB="bitnow"
RDS_USER="master"
RDS_PASSWORD="5631athp"

# 백업 파일명
BACKUP_FILE="backups/bitnow_backup_$(date +%Y%m%d_%H%M%S).sql"

# backups 디렉토리 생성
mkdir -p backups

echo "📦 데이터베이스 덤프 생성 중..."
# PostgreSQL 16 바이너리 경로 사용
PG_DUMP_PATH="/opt/homebrew/opt/postgresql@16/bin/pg_dump"

PGPASSWORD=$RDS_PASSWORD $PG_DUMP_PATH \
  -h $RDS_HOST \
  -p $RDS_PORT \
  -U $RDS_USER \
  -d $RDS_DB \
  -f $BACKUP_FILE \
  --verbose \
  --no-owner \
  --no-privileges

echo "✅ 백업 완료: $BACKUP_FILE"
echo "📊 백업 파일 크기: $(du -h $BACKUP_FILE | cut -f1)"

echo "🔍 백업 내용 요약:"
echo "- 테이블 수: $(grep -c "CREATE TABLE" $BACKUP_FILE || echo "0")"
echo "- INSERT 문 수: $(grep -c "INSERT INTO" $BACKUP_FILE || echo "0")"