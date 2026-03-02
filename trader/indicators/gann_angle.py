"""gann_angle.py — 1×1 Gann Angle (자동 스케일)

1×1 Gann Angle:
  - 기울기(slope) = (최근 N bar 고가-저가 범위) / N
  - 라인: P0 + slope * (t - t0)
  - trend_ok = Close[t] >= line_1x1
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def compute_gann_slope(
    df: pd.DataFrame,
    current_idx: int,
    scale_n: int = 90,
) -> float:
    """최근 scale_n 바의 가격 범위로 1×1 Gann 기울기를 계산한다.

    slope = (max(High) - min(Low)) / scale_n

    Args:
        df: OHLCV DataFrame
        current_idx: 현재 바의 iloc 위치
        scale_n: 스케일 윈도우 크기 (기본 90)

    Returns:
        slope (가격/바)
    """
    start = max(0, current_idx - scale_n + 1)
    end = current_idx + 1

    highs = df["High"].iloc[start:end]
    lows = df["Low"].iloc[start:end]

    if len(highs) == 0:
        return 0.0

    price_range = highs.max() - lows.min()
    actual_bars = len(highs)

    return price_range / actual_bars if actual_bars > 0 else 0.0


def gann_1x1_line(
    pivot_price: float,
    pivot_iloc: int,
    current_idx: int,
    slope: float,
) -> float:
    """1×1 Gann Angle 라인 값을 계산한다.

    line_1x1 = P0 + slope * (t - t0)
    """
    return pivot_price + slope * (current_idx - pivot_iloc)


def is_trend_ok(
    df: pd.DataFrame,
    current_idx: int,
    pivot_price: float,
    pivot_iloc: int,
    scale_n: int = 90,
) -> bool:
    """현재 바에서 1×1 Gann Angle 위에 있는지 판별한다.

    trend_ok = Close[t] >= line_1x1

    Args:
        df: OHLCV DataFrame
        current_idx: 현재 바의 iloc 위치
        pivot_price: 앵커 가격 (P0)
        pivot_iloc: 앵커의 iloc 위치
        scale_n: Gann 스케일 윈도우

    Returns:
        True 이면 롱 우호 트렌드
    """
    slope = compute_gann_slope(df, current_idx, scale_n)
    line_val = gann_1x1_line(pivot_price, pivot_iloc, current_idx, slope)
    close = df["Close"].iloc[current_idx]
    return close >= line_val
