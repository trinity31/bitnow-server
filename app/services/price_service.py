import asyncio
import time
import aiohttp
from typing import Dict, Any, Tuple


async def get_upbit_price() -> Tuple[float, float]:
    """업비트 API에서 BTC-KRW 가격과 변동률을 조회합니다."""
    url = "https://api.upbit.com/v1/ticker?markets=KRW-BTC"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            price = float(data[0]["trade_price"])
            percent_change = float(data[0]["change_rate"]) * 100
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


async def get_krw_price() -> Dict[str, Any]:
    """BTC의 원화 가격과 변동률을 조회합니다."""
    price, change = await get_upbit_price()
    return {
        "btc_krw": price,
        "percent_change_24h": change,
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
    """BTC의 원화와 달러 가격, 그리고 각각의 변동률을 동시에 조회합니다."""
    (krw_price, krw_change), (usd_price, usd_change) = await asyncio.gather(
        get_upbit_price(), get_binance_price()
    )

    return {
        "btc_krw": krw_price,
        "btc_usd": usd_price,
        "krw_change_24h": krw_change,
        "usd_change_24h": usd_change,
        "timestamp": int(time.time()),
    }
