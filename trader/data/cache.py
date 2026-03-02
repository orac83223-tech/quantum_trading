"""cache.py — Parquet 캐시 읽기/쓰기"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from trader.config import get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


def _cache_dir() -> Path:
    cfg = get_config()
    p = cfg.cache_path
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_path_for(ticker: str) -> Path:
    """티커에 대응하는 parquet 파일 경로."""
    return _cache_dir() / f"{ticker}.parquet"


def read_cache(ticker: str) -> Optional[pd.DataFrame]:
    """캐시에서 OHLCV DataFrame 을 읽는다. 없으면 None."""
    p = cache_path_for(ticker)
    if not p.exists():
        return None
    try:
        df = pd.read_parquet(p)
        log.debug("캐시 로드: %s (%d rows)", ticker, len(df))
        return df
    except Exception as exc:
        log.warning("캐시 읽기 실패 %s: %s", ticker, exc)
        return None


def write_cache(ticker: str, df: pd.DataFrame) -> None:
    """OHLCV DataFrame 을 parquet 으로 저장한다."""
    if df.empty:
        return
    p = cache_path_for(ticker)
    df.to_parquet(p, engine="pyarrow", compression="snappy")
    log.debug("캐시 저장: %s (%d rows)", ticker, len(df))


def load_or_fetch(
    ticker: str,
    start_date: date,
    end_date: date,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """캐시 우선 로드, 없으면 pykrx 에서 수집 후 캐시에 저장.

    force_refresh=True 이면 항상 새로 수집.
    """
    from trader.data.pykrx_loader import fetch_ohlcv

    if not force_refresh:
        cached = read_cache(ticker)
        if cached is not None:
            # 요청 범위 내 데이터가 있는지 확인
            cached_start = cached.index.min().date() if hasattr(cached.index.min(), 'date') else cached.index.min()
            cached_end = cached.index.max().date() if hasattr(cached.index.max(), 'date') else cached.index.max()

            if cached_start <= start_date and cached_end >= end_date:
                mask = (cached.index >= pd.Timestamp(start_date)) & (
                    cached.index <= pd.Timestamp(end_date)
                )
                return cached.loc[mask]

            # 캐시 범위가 부족하면 전체 구간을 다시 수집
            log.info(
                "캐시 범위 부족 %s: 캐시(%s~%s), 요청(%s~%s)",
                ticker, cached_start, cached_end, start_date, end_date,
            )

    # 수집
    df = fetch_ohlcv(ticker, start_date, end_date)
    if not df.empty:
        # 기존 캐시와 병합
        cached = read_cache(ticker)
        if cached is not None and not cached.empty:
            df = pd.concat([cached, df])
            df = df[~df.index.duplicated(keep="last")]
            df = df.sort_index()
        write_cache(ticker, df)

    return df
