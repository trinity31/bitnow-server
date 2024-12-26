from fastapi import APIRouter, HTTPException
from app.services.price_service import get_current_prices, get_krw_price, get_usd_price

router = APIRouter()


@router.get("/prices")
async def get_prices():
    """
    BTC의 현재 원화(KRW)와 달러(USD) 가격, 각각의 24시간 변동률, 김치 프리미엄을 조회합니다.

    Returns:
        dict: {
            "btc_krw": float,  # 원화 가격
            "btc_usd": float,  # 달러 가격
            "krw_change_24h": float,  # KRW 마켓 24시간 변동률 (%)
            "usd_change_24h": float,  # USD 마켓 24시간 변동률 (%)
            "kimchi_premium": float,  # 김치 프리미엄 (%)
            "timestamp": int    # 타임스탬프
        }
    """
    try:
        prices = await get_current_prices()
        return prices
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prices/krw")
async def get_krw_prices():
    """
    BTC의 현재 원화(KRW) 가격, 24시간 변동률, 김치 프리미엄을 조회합니다.

    Returns:
        dict: {
            "btc_krw": float,  # 원화 가격
            "percent_change_24h": float,  # 24시간 변동률 (%)
            "kimchi_premium": float,  # 김치 프리미엄 (%)
            "timestamp": int    # 타임스탬프
        }
    """
    try:
        price = await get_krw_price()
        return price
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prices/usd")
async def get_usd_prices():
    """
    BTC의 현재 달러(USD) 가격과 24시간 변동률을 조회합니다.

    Returns:
        dict: {
            "btc_usd": float,  # 달러 가격
            "percent_change_24h": float,  # 24시간 변동률 (%)
            "timestamp": int    # 타임스탬프
        }
    """
    try:
        price = await get_usd_price()
        return price
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
