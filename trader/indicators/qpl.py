"""qpl.py — Quantum Price Lines (QPL) 계산

Fabio Oreste 모델의 단순화된 QPL 버전.
Pivot Low 앵커(P0)를 기준으로 과거 변동성(ATR 비율)을 통해
비선형(로그) 지지/저항 조화 레벨을 생성한다.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

import pandas as pd


def compute_qpl_levels(
    anchor_price: float,
    volatility_pct: float,
    n_levels: int = 5,
) -> List[float]:
    """기준 가격과 변동성을 바탕으로 QPL 레벨(위/아래)을 계산한다.

    QPL_n = P0 * exp(n * volatility_pct)  for n in [-n_levels, ..., n_levels]

    Args:
        anchor_price: 앵커 가격 (P0, Pivot Low)
        volatility_pct: 기준 변동성 (예: ATR / Close)
        n_levels: 위/아래로 생성할 레벨 개수

    Returns:
        정렬된 QPL 가격 레벨 리스트
    """
    levels = set()
    levels.add(anchor_price)

    vol = max(volatility_pct, 0.001)  # 최소 0.1% 변동성 보장

    for n in range(1, n_levels + 1):
        # 상승/하락 비율
        up_factor = math.exp(n * vol)
        down_factor = math.exp(-n * vol)

        up_level = anchor_price * up_factor
        down_level = anchor_price * down_factor

        levels.add(round(up_level, 2))
        if down_level > 0:
            levels.add(round(down_level, 2))

    return sorted(list(levels))


def find_nearest_qpl(
    current_price: float,
    anchor_price: float,
    volatility_pct: float,
    n_levels: int = 5,
) -> Tuple[Optional[float], Optional[float]]:
    """현재가 기준으로 가장 가까운 QPL 하단(Ls_qpl)과 상단(Lr_qpl)을 반환.

    Args:
        current_price: 현재가
        anchor_price: 앵커 가격
        volatility_pct: 변동성
        n_levels: 레벨 수

    Returns:
        (하단 QPL, 상단 QPL). 범위를 벗어나면 None.
    """
    levels = compute_qpl_levels(anchor_price, volatility_pct, n_levels)

    lower = [lv for lv in levels if lv <= current_price]
    upper = [lv for lv in levels if lv > current_price]

    Ls = max(lower) if lower else None
    Lr = min(upper) if upper else None

    return Ls, Lr
