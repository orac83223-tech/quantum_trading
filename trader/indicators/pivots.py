"""pivots.py — Pivot Low(3,3) — t+3 확정 로직

핵심 원칙: Look-ahead 방지
  - Low[t] 가 Low[t-3..t+3] 구간의 최저이면 피벗 로우 후보
  - 하지만 t+3 시점이 되어야 비로소 확정
  - 따라서 '현재 바' 기준으로 사용할 수 있는 피벗 로우는
    최소 3 bars 전에 확정된 것만 허용
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


def detect_pivot_lows(
    lows: pd.Series,
    left: int = 3,
    right: int = 3,
) -> pd.Series:
    """피벗 로우 후보를 감지한다.

    pivot_low[i] = True  iff  Low[i] == min(Low[i-left..i+right])
    (양 끝 포함)

    Returns:
        Boolean 시리즈 (True = 피벗 로우 후보)
    """
    n = len(lows)
    is_pivot = pd.Series(False, index=lows.index)
    values = lows.values

    for i in range(left, n - right):
        window = values[i - left : i + right + 1]
        if values[i] == np.nanmin(window):
            is_pivot.iloc[i] = True

    return is_pivot


def confirmed_pivot_lows(
    lows: pd.Series,
    left: int = 3,
    right: int = 3,
) -> pd.Series:
    """확정된 피벗 로우만 표시한다.

    피벗 로우가 i에서 발생하면 i+right 시점(확정 시점) 이후에만
    사용 가능하다. 이 함수는 '확정 시점' 기준 Boolean 을 반환한다.

    confirmed[i + right] = True  (i에서 피벗 발생, i+right에서 확정)

    Returns:
        Boolean 시리즈 (True = 해당 바에서 피벗이 확정됨)
    """
    raw = detect_pivot_lows(lows, left, right)
    confirmed = pd.Series(False, index=lows.index)

    pivot_indices = raw[raw].index
    for pidx in pivot_indices:
        loc = lows.index.get_loc(pidx)
        confirm_loc = loc + right
        if confirm_loc < len(lows):
            confirmed.iloc[confirm_loc] = True

    return confirmed


def get_latest_confirmed_pivot(
    df: pd.DataFrame,
    current_idx: int,
    left: int = 3,
    right: int = 3,
) -> Optional[Tuple[int, float, int]]:
    """current_idx 시점에서 가장 최근에 확정된 피벗 로우를 반환한다.

    Look-ahead 방지:
      - 피벗 후보가 bar i 에서 발생했으면, i + right 시점에서 확정
      - current_idx >= i + right 인 피벗만 사용 가능

    Args:
        df: OHLCV DataFrame
        current_idx: 현재 바의 정수 위치 (iloc 기준)
        left: 왼쪽 피벗 윈도우
        right: 오른쪽 피벗 윈도우

    Returns:
        (pivot_iloc, pivot_price, pivot_bar_index) 또는 None
        - pivot_iloc: 피벗이 발생한 iloc 위치
        - pivot_price: 피벗 가격 (Low)
        - pivot_bar_index: 전체 df 내 피벗 날짜 (index)
    """
    lows = df["Low"]
    values = lows.values

    best_pivot_iloc: Optional[int] = None
    best_price: Optional[float] = None

    # current_idx 에서 확인 가능한 가장 늦은 피벗 후보: current_idx - right
    max_candidate = current_idx - right

    for i in range(left, max_candidate + 1):
        # i 가 피벗 로우인지 판별
        window_start = i - left
        window_end = min(i + right + 1, len(values))
        window = values[window_start:window_end]

        if len(window) < left + right + 1:
            continue

        if values[i] == np.nanmin(window):
            # 유효한 피벗 → 가장 최근 것으로 갱신
            if best_pivot_iloc is None or i > best_pivot_iloc:
                best_pivot_iloc = i
                best_price = values[i]

    if best_pivot_iloc is not None:
        return (best_pivot_iloc, best_price, df.index[best_pivot_iloc])

    return None
