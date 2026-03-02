"""pykrx_loader.py — 코스닥 티커 목록 + OHLCV 수집"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Optional

import pandas as pd
from pykrx import stock as pykrx_stock

from trader.config import AppConfig, get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


def get_market_tickers(market: str, ref_date: Optional[date] = None) -> List[str]:
    """ref_date 기준 특정 마켓(KOSPI/KOSDAQ)의 전체 티커 목록을 반환한다."""
    if ref_date is None:
        ref_date = date.today()
    dt_str = ref_date.strftime("%Y%m%d")
    market = market.upper()
    
    tickers = pykrx_stock.get_market_ticker_list(dt_str, market=market)
    log.info("%s 티커 %d 종목 조회 (기준일: %s)", market, len(tickers), ref_date)
    return tickers


def get_ticker_name(ticker: str, ref_date: Optional[date] = None) -> str:
    """티커의 종목명을 반환한다."""
    if ref_date is None:
        ref_date = date.today()
    dt_str = ref_date.strftime("%Y%m%d")
    return pykrx_stock.get_market_ticker_name(ticker)


def fetch_ohlcv(
    ticker: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    """pykrx 에서 일봉 OHLCV 데이터를 가져온다.

    Returns:
        DataFrame with columns: ['Open', 'High', 'Low', 'Close', 'Volume', 'Value']
        index: DatetimeIndex (date)
    """
    s = start_date.strftime("%Y%m%d")
    e = end_date.strftime("%Y%m%d")

    df = pykrx_stock.get_market_ohlcv_by_date(s, e, ticker)

    if df.empty:
        log.warning("OHLCV 데이터 없음: %s (%s ~ %s)", ticker, start_date, end_date)
        return pd.DataFrame()

    # 컬럼명 영문 통일
    col_map = {
        "시가": "Open",
        "고가": "High",
        "저가": "Low",
        "종가": "Close",
        "거래량": "Volume",
        "거래대금": "Value",
    }
    df = df.rename(columns=col_map)

    # 필요한 컬럼만 유지
    keep = ["Open", "High", "Low", "Close", "Volume", "Value"]
    df = df[[c for c in keep if c in df.columns]]

    # 거래량 0인 날(거래정지) 제거
    if "Volume" in df.columns:
        df = df[df["Volume"] > 0]

    return df


def filter_universe(
    tickers: List[str],
    ohlcv_map: Dict[str, pd.DataFrame],
    cfg: Optional[AppConfig] = None,
) -> List[str]:
    """유니버스 필터를 적용하여 유효 종목만 반환한다.

    조건:
      1. 최소 상장일수 (min_listed_days)
      2. 최소 평균 거래대금 (min_value_krw, 최근 60일)
      3. 최소 종가 (min_price)
      4. exclude_list 수동 제외
    """
    if cfg is None:
        cfg = get_config()

    uc = cfg.universe
    passed: List[str] = []

    for ticker in tickers:
        # 수동 제외 목록
        if ticker in uc.exclude_list:
            continue

        df = ohlcv_map.get(ticker)
        if df is None or df.empty:
            continue

        # 최소 상장일수
        if len(df) < uc.min_listed_days:
            continue

        # 최소 종가
        last_close = df["Close"].iloc[-1]
        if last_close < uc.min_price:
            continue

        # 최소 평균 거래대금 (최근 60일)
        if "Value" in df.columns:
            recent_value = df["Value"].tail(60).mean()
            if recent_value < uc.min_value_krw:
                continue

        passed.append(ticker)

    log.info("유니버스 필터 통과: %d / %d", len(passed), len(tickers))
    return passed
