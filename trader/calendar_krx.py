"""calendar_krx.py — KRX 거래일 캘린더 (주말/휴일 제외)"""

from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache
from typing import List, Optional

import pandas as pd


@lru_cache(maxsize=32)
def _fetch_krx_trading_days(year: int) -> List[date]:
    """pykrx 를 통해 해당 연도의 KRX 거래일 목록을 가져온다."""
    from pykrx import stock as pykrx_stock

    start = f"{year}0101"
    end = f"{year}1231"
    # get_previous_business_days 대신 실제 OHLCV 존재일 기반
    try:
        days = pykrx_stock.get_market_ohlcv_by_date(start, end, "005930")
        return sorted(days.index.date.tolist())
    except Exception:
        # 폴백: 주말만 제외
        return _weekday_fallback(year)


def _weekday_fallback(year: int) -> List[date]:
    """KRX 데이터 없을 때 주말만 제외한 거래일 리스트."""
    d = date(year, 1, 1)
    end = date(year, 12, 31)
    days = []
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def get_trading_days(start_date: date, end_date: date) -> List[date]:
    """start_date ~ end_date 범위의 KRX 거래일 리스트를 반환한다."""
    years = range(start_date.year, end_date.year + 1)
    all_days: List[date] = []
    for y in years:
        all_days.extend(_fetch_krx_trading_days(y))
    return sorted(d for d in all_days if start_date <= d <= end_date)


def offset_trading_day(ref_date: date, offset: int) -> date:
    """ref_date 기준으로 offset 거래일만큼 이동한 날짜를 반환한다.

    offset > 0: 미래  offset < 0: 과거
    """
    year = ref_date.year
    days = _fetch_krx_trading_days(year)

    # 연도 경계 처리를 위해 앞뒤 연도 포함
    if offset > 0:
        days += _fetch_krx_trading_days(year + 1)
    elif offset < 0:
        days = _fetch_krx_trading_days(year - 1) + days

    days = sorted(set(days))

    try:
        idx = next(i for i, d in enumerate(days) if d >= ref_date)
    except StopIteration:
        return ref_date

    target_idx = idx + offset
    if 0 <= target_idx < len(days):
        return days[target_idx]
    return ref_date


def count_trading_days(start_date: date, end_date: date) -> int:
    """start_date ~ end_date 사이의 거래일 수를 반환한다 (양 끝 포함)."""
    return len(get_trading_days(start_date, end_date))
