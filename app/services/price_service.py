import asyncio
import time
import aiohttp
from typing import Dict, Any, Tuple
from app.services.exchange_service import exchange_service
import logging
from langchain_openai import ChatOpenAI
import os

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
    """BTC/USDT의 이동평균선 돌파 여부 확인 및 시장 상태 진단"""
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

        # GPT-4를 통한 시장 상태 진단
        market_diagnosis = await analyze_market_state(ma_results, day1_close)

        # 최종 반환에 진단 결과 추가
        return {
            "price": day1_close,
            "timestamp": int(time.time()),
            "ma_results": ma_results,
            "market_diagnosis": market_diagnosis,
        }

    except Exception as e:
        logger.error(f"Failed to check multiple MAs cross: {str(e)}")
        return {"error": str(e), "timestamp": int(time.time())}


async def analyze_market_state(
    ma_results: Dict[int, Dict[str, Any]], current_price: float
) -> Dict[str, str]:
    """이동평균선 데이터를 기반으로 GPT-4로 시장 상태 진단"""
    try:
        # MA 값들 정렬
        ma_values = {period: data["ma_value"] for period, data in ma_results.items()}

        # 현재가와 MA들의 위치 관계 분석
        price_relations = {
            "ma20": current_price / ma_values[20] - 1,  # 퍼센트로 변환
            "ma60": current_price / ma_values[60] - 1,
            "ma120": current_price / ma_values[120] - 1,
            "ma200": current_price / ma_values[200] - 1,
        }

        # MA 간의 관계 분석
        ma_relations = {
            "ma20_60": ma_values[20] / ma_values[60] - 1,
            "ma60_120": ma_values[60] / ma_values[120] - 1,
            "ma120_200": ma_values[120] / ma_values[200] - 1,
        }

        # GPT-4 프롬프트 구성
        prompt = f"""
현재 비트코인의 이동평균선 상태를 분석해주세요:

현재가와 이동평균선의 관계:
- 20일선 대비: {price_relations['ma20']:.2%}
- 60일선 대비: {price_relations['ma60']:.2%}
- 120일선 대비: {price_relations['ma120']:.2%}
- 200일선 대비: {price_relations['ma200']:.2%}

이동평균선 간의 관계:
- 20일선/60일선: {ma_relations['ma20_60']:.2%}
- 60일선/120일선: {ma_relations['ma60_120']:.2%}
- 120일선/200일선: {ma_relations['ma120_200']:.2%}

위 데이터를 바탕으로 현재 시장 상태를 간단히 진단하고, 향후 전망을 제시해주세요.
응답은 반드시 다음 형식으로 해주세요:
{{"trend": "현재 추세를 한 단어로", "description": "상세 설명을 1-2문장으로"}}
"""

        # GPT-4 호출
        chat = ChatOpenAI(
            model="gpt-4o-mini", temperature=0, api_key=os.getenv("OPENAI_API_KEY")
        )

        response = chat.invoke(prompt)

        # 응답 파싱 (GPT가 JSON 형식으로 응답했다고 가정)
        import json

        result = json.loads(response.content)

        return result

    except Exception as e:
        logger.error(f"GPT analysis failed: {str(e)}")
        # GPT 분석 실패시 기본 분석 결과 반환
        return {
            "trend": "분석 불가",
            "description": "이동평균선 분석은 가능하나 GPT 상세 분석에 실패했습니다.",
        }
