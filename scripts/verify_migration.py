#!/usr/bin/env python3
"""
데이터베이스 마이그레이션 후 데이터 검증 스크립트
"""
import asyncio
import os
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

async def verify_migration():
    """마이그레이션 후 데이터 검증"""
    
    # 기존 AWS RDS
    old_url = "postgresql+asyncpg://master:5631athp@bitnow-db-instance.c5k2y4ksghoa.ap-northeast-2.rds.amazonaws.com:5432/bitnow"
    
    # 새로운 Railway 데이터베이스 URL (환경 변수에서 가져오기)
    new_url = os.getenv("RAILWAY_DATABASE_URL") or os.getenv("PROD_DATABASE_URL")
    
    if not new_url:
        print("❌ RAILWAY_DATABASE_URL 또는 PROD_DATABASE_URL 환경 변수가 설정되지 않았습니다.")
        print("Railway 마이그레이션 검증을 위해 RAILWAY_DATABASE_URL을 설정해주세요.")
        return
    
    old_engine = create_async_engine(old_url)
    new_engine = create_async_engine(new_url)
    
    tables_to_check = ['users', 'alerts', 'credits', 'credit_histories', 'mvrv_indicators', 'fear_greed_indicators']
    
    try:
        print("🔍 데이터베이스 마이그레이션 검증 시작...")
        
        for table in tables_to_check:
            # 기존 DB 레코드 수
            async with old_engine.begin() as old_conn:
                old_result = await old_conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                old_count = old_result.scalar()
            
            # 새 DB 레코드 수  
            async with new_engine.begin() as new_conn:
                new_result = await new_conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                new_count = new_result.scalar()
            
            if old_count == new_count:
                print(f"✅ {table}: {old_count} = {new_count}")
            else:
                print(f"❌ {table}: {old_count} != {new_count}")
        
        print("\n🎉 마이그레이션 검증 완료!")
        
    except Exception as e:
        print(f"❌ 검증 중 오류 발생: {e}")
    
    finally:
        await old_engine.dispose()
        await new_engine.dispose()

if __name__ == "__main__":
    asyncio.run(verify_migration())