import asyncio
import time
import aiohttp
from typing import Dict, Any, Tuple
from app.services.exchange_service import exchange_service
import logging

logger = logging.getLogger(__name__)


async def get_upbit_price() -> Tuple[float, float]:
    """업비트 API에서 BTC-KRW 가격과 변동률을 조회합니다."""
    url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            price = float(data[0]["trade_price"])
            percent_change = float(data[0]["signed_change_rate"]) * 100
            return price, percent_change


async def get_binance_price() -> Tuple[float, float]:
    """바이낸스 API에서 BTC-USDT 가격과 변동률을 조회합니다."""
    url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            price = float(data["lastPrice"])
            percent_change = float(data["priceChangePercent"])
            return price, percent_change


async def calculate_kimchi_premium(krw_price: float, usd_price: float) -> float:
    """
    김치 프리미엄을 계산합니다.
    계산식: ((업비트가격 - (바이낸스가격 * 환율)) / (바이낸스가격 * 환율)) * 100
    """
    exchange_rate = await exchange_service.get_usd_krw_rate()
    binance_krw = usd_price * exchange_rate
    kimchi_premium = ((krw_price - binance_krw) / binance_krw) * 100

    return round(kimchi_premium, 2)


async def get_krw_price() -> Dict[str, Any]:
    """BTC의 원화 가격과 변동률, 김치 프리미엄을 조회합니다."""
    krw_price, krw_change = await get_upbit_price()
    usd_price, _ = await get_binance_price()

    kimchi_premium = await calculate_kimchi_premium(krw_price, usd_price)

    return {
        "btc_krw": krw_price,
        "percent_change_24h": krw_change,
        "kimchi_premium": kimchi_premium,
        "timestamp": int(time.time()),
    }


async def get_usd_price() -> Dict[str, Any]:
    """BTC의 달러 가격과 변동률을 조회합니다."""
    price, change = await get_binance_price()
    return {
        "btc_usd": price,
        "percent_change_24h": change,
        "timestamp": int(time.time()),
    }


async def get_current_prices() -> Dict[str, Any]:
    """BTC의 원화와 달러 가격, 변동률, 김치 프리미엄을 동시에 조회합니다."""
    (krw_price, krw_change), (usd_price, usd_change) = await asyncio.gather(
        get_upbit_price(), get_binance_price()
    )

    print("\n=== 가격 정보 ===")
    kimchi_premium = await calculate_kimchi_premium(krw_price, usd_price)

    return {
        "btc_krw": krw_price,
        "btc_usd": usd_price,
        "krw_change_24h": krw_change,
        "usd_change_24h": usd_change,
        "kimchi_premium": kimchi_premium,
        "timestamp": int(time.time()),
    }


import aiohttp
import time
from typing import Any, Dict, List

# 원하는 이동평균 기간 목록
MA_PERIODS = [20, 60, 120, 200]


async def check_ma_cross_all() -> Dict[str, Any]:
    """
    BTC/USDT에 대해 20일, 60일, 120일, 200일 등
    다양한 이동평균선 돌파 여부(±2% & 2일 연속 유지)를 확인
    """
    try:
        url = "https://api.binance.com/api/v3/klines"

        # 가장 긴 이동평균 기간이 200일이므로, 안전하게 250~300개 정도 가져오기
        # (최대 기간 + 예비 데이터)
        params = {"symbol": "BTCUSDT", "interval": "1d", "limit": 300}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status != 200:
                    raise ValueError(f"Binance API returned status {response.status}")
                data = await response.json()

        # 일봉의 종가(4번 인덱스) 추출
        closes = [float(candle[4]) for candle in data]

        # 최소한 가장 긴 MA(200일)를 계산할 수 있어야 함
        if len(closes) < max(MA_PERIODS):
            raise ValueError(
                f"Not enough data to calculate max MA({max(MA_PERIODS)} days). Got {len(closes)} days."
            )

        # 최근 N=3일간 종가 추출 (2일 연속 여부 확인용)
        #   - day2_close: 바로 전날 종가
        #   - day1_close: 현재(가장 최근) 종가
        #   (day3_close는 필요 시 확장 분석용)
        day3_close = closes[-3]
        day2_close = closes[-2]
        day1_close = closes[-1]

        # 결과 저장용 딕셔너리
        # ma_results[period] = {
        #    "ma_value": ...,
        #    "threshold_up": ...,
        #    "threshold_down": ...,
        #    "confirmed_up": ...,
        #    "confirmed_down": ...
        # }
        ma_results: Dict[int, Dict[str, Any]] = {}

        for period in MA_PERIODS:
            # period일 SMA 계산
            ma_value = sum(closes[-period:]) / period

            # ±2% 기준
            threshold_up = ma_value * 1.02
            threshold_down = ma_value * 0.98

            # 2일 연속 ±2% 돌파 여부
            def is_confirmed_up(price_list: List[float]) -> bool:
                return all(price > threshold_up for price in price_list)

            def is_confirmed_down(price_list: List[float]) -> bool:
                return all(price < threshold_down for price in price_list)

            last_two_days = [day2_close, day1_close]

            confirmed_up = is_confirmed_up(last_two_days)
            confirmed_down = is_confirmed_down(last_two_days)

            ma_results[period] = {
                "ma_value": ma_value,
                "threshold_up": threshold_up,
                "threshold_down": threshold_down,
                "confirmed_up": confirmed_up,  # 2일 연속 +2% 이상 상회
                "confirmed_down": confirmed_down,  # 2일 연속 -2% 이하 하회
            }

        logger.info(f"MA 결과: {ma_results}")

        # 최종 반환 (현재 가격, 타임스탬프, 기간별 MA 결과)
        return {
            "price": day1_close,
            "timestamp": int(time.time()),
            "ma_results": ma_results,
        }

    except Exception as e:
        logger.error(f"Failed to check multiple MAs cross: {str(e)}")
        return {"error": str(e), "timestamp": int(time.time())}
