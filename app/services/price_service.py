import asyncio
import time
import aiohttp
from typing import Dict, Any, Tuple
from app.services.exchange_service import exchange_service


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
