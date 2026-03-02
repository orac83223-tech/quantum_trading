"""math.py — 공통 수학 유틸"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd


def safe_sqrt(x: float) -> float:
    """음수-안전 제곱근. x < 0 이면 0을 반환."""
    return math.sqrt(max(x, 0.0))


def nearest_levels(
    price: float,
    levels: List[float],
) -> Tuple[Optional[float], Optional[float]]:
    """price 기준으로 가장 가까운 하단(support) 레벨과 상단(resistance) 레벨을 반환.

    Returns:
        (Ls, Lr) — 하단/상단 레벨. 존재하지 않으면 None.
    """
    lower = [lv for lv in levels if lv <= price]
    upper = [lv for lv in levels if lv > price]

    Ls = max(lower) if lower else None
    Lr = min(upper) if upper else None
    return Ls, Lr


def sma(series: pd.Series, period: int) -> pd.Series:
    """단순 이동 평균."""
    return series.rolling(window=period, min_periods=period).mean()
