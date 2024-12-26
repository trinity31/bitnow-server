import aiohttp
from typing import Optional
from datetime import datetime, timedelta
from app.constants import DEFAULT_USD_KRW_RATE, CACHE_DURATION_HOURS


class ExchangeRateService:
    def __init__(self):
        self.base_url = "https://api.exchangerate-api.com/v4/latest/USD"
        self._cached_rate: Optional[float] = None
        self._last_updated: Optional[datetime] = None

    async def get_usd_krw_rate(self) -> float:
        """USD/KRW 환율을 조회합니다. 1시간 캐시를 사용합니다."""
        # 캐시된 환율이 있고 1시간이 지나지 않았다면 캐시된 값을 반환
        if (
            self._cached_rate
            and self._last_updated
            and datetime.now() - self._last_updated
            < timedelta(hours=CACHE_DURATION_HOURS)
        ):
            return self._cached_rate

        # 새로운 환율 조회
        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url) as response:
                if response.status != 200:
                    # API 오류 시 기본값 사용
                    return DEFAULT_USD_KRW_RATE

                data = await response.json()
                rate = float(data["rates"]["KRW"])

                print(f"조회된 환율: {rate}")

                # 캐시 업데이트
                self._cached_rate = rate
                self._last_updated = datetime.now()
                return rate


# 싱글톤 인스턴스 생성
exchange_service = ExchangeRateService()
