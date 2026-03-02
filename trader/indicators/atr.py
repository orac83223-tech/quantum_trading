"""atr.py — ATR(14) Wilder 방식"""

from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range 를 계산한다.

    Args:
        df: OHLCV DataFrame (컬럼: High, Low, Close)
    """
    high = df["High"]
    low = df["Low"]
    prev_close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    return pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder 방식 ATR(Average True Range)을 계산한다.

    첫 period 구간은 단순 평균, 이후 지수 이동 평균(Wilder smoothing).

    Args:
        df: OHLCV DataFrame
        period: ATR 기간 (기본 14)

    Returns:
        ATR 시리즈
    """
    tr = true_range(df)

    # Wilder smoothing: ATR[t] = ATR[t-1] * (n-1)/n + TR[t] / n
    atr_values = np.full(len(tr), np.nan)

    # 첫 period 구간: 단순 평균
    first_valid = tr.first_valid_index()
    if first_valid is None:
        return pd.Series(atr_values, index=df.index, name="ATR")

    start_loc = tr.index.get_loc(first_valid)

    if start_loc + period > len(tr):
        return pd.Series(atr_values, index=df.index, name="ATR")

    atr_values[start_loc + period - 1] = tr.iloc[start_loc : start_loc + period].mean()

    # Wilder smoothing
    for i in range(start_loc + period, len(tr)):
        atr_values[i] = (atr_values[i - 1] * (period - 1) + tr.iloc[i]) / period

    return pd.Series(atr_values, index=df.index, name="ATR")
