import aiohttp
from typing import Optional
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from app.constants import DEFAULT_USD_KRW_RATE, CACHE_DURATION_HOURS

# .env 파일에서 환경변수 로드
load_dotenv()


class ExchangeRateService:
    def __init__(self):
        self.base_url = (
            "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"
        )
        self.api_key = os.getenv("EXCHANGE_API_KEY")
        self._cached_rate: Optional[float] = None
        self._last_updated: Optional[datetime] = None

    def _is_cache_valid(self) -> bool:
        """캐시가 유효한지 확인합니다."""
        return (
            self._cached_rate is not None
            and self._last_updated is not None
            and datetime.now() - self._last_updated
            < timedelta(hours=CACHE_DURATION_HOURS)
        )

    def _update_cache(self, rate: float) -> None:
        """환율 캐시를 업데이트합니다."""
        self._cached_rate = rate
        self._last_updated = datetime.now()
        print(f"조회된 환율: {rate}")

    async def get_usd_krw_rate(self) -> float:
        """USD/KRW 환율을 조회합니다. 1시간 캐시를 사용합니다."""
        if self._is_cache_valid():
            return self._cached_rate

        params = {
            "authkey": self.api_key,
            "searchdate": datetime.now().strftime("%Y%m%d"),
            "data": "AP01",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(self.base_url, params=params) as response:
                if response.status != 200:
                    return DEFAULT_USD_KRW_RATE

                data = await response.json()
                if not data or not isinstance(data, list):
                    return DEFAULT_USD_KRW_RATE

                for item in data:
                    if item.get("cur_unit") == "USD":
                        # 송금받을때 환율(tts) 사용
                        rate = float(item["tts"].replace(",", ""))
                        self._update_cache(rate)
                        return rate

                return DEFAULT_USD_KRW_RATE


# 싱글톤 인스턴스 생성
exchange_service = ExchangeRateService()
