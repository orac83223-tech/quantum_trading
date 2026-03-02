"""so9.py — Square of 9 레벨 계산

Fabio Oreste 의 Quantum Trading 에서 제시한 Square of 9 가격 레벨을
앵커 가격(Pivot Low P0) 기반으로 계산한다.

수식:
  r = sqrt(P0)
  for k in k_cycles:
      for angle in angles:
          delta = angle / 360
          upper = (r + k + delta) ** 2
          lower = (r - k - delta) ** 2
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

from trader.utils.math import safe_sqrt


def compute_so9_levels(
    anchor_price: float,
    angles: Optional[List[int]] = None,
    k_cycles: Optional[List[int]] = None,
) -> List[float]:
    """앵커 가격 기반 Square of 9 레벨 목록을 반환한다.

    Args:
        anchor_price: 앵커 가격 (P0, Pivot Low)
        angles: 각도 리스트 (기본: [45, 90, 135, 180, 270, 360])
        k_cycles: 사이클 리스트 (기본: [0, 1])

    Returns:
        정렬된 레벨 리스트 (중복 제거, 양수만)
    """
    if angles is None:
        angles = [45, 90, 135, 180, 270, 360]
    if k_cycles is None:
        k_cycles = [0, 1]

    r = safe_sqrt(anchor_price)
    levels: set = set()

    for k in k_cycles:
        for angle in angles:
            delta = angle / 360.0

            upper = (r + k + delta) ** 2
            lower_val = r - k - delta
            lower = lower_val ** 2 if lower_val > 0 else 0.0

            if upper > 0:
                levels.add(round(upper, 2))
            if lower > 0:
                levels.add(round(lower, 2))

    return sorted(levels)


def find_support_resistance(
    current_price: float,
    anchor_price: float,
    angles: Optional[List[int]] = None,
    k_cycles: Optional[List[int]] = None,
) -> Tuple[Optional[float], Optional[float]]:
    """현재가 기준으로 가장 가까운 So9 지지선(Ls)과 저항선(Lr)을 반환.

    Args:
        current_price: 현재 가격
        anchor_price: 앵커 가격 (P0)

    Returns:
        (Ls, Lr) — (support, resistance). 해당 없으면 None.
    """
    levels = compute_so9_levels(anchor_price, angles, k_cycles)

    Ls: Optional[float] = None
    Lr: Optional[float] = None

    for lv in levels:
        if lv <= current_price:
            if Ls is None or lv > Ls:
                Ls = lv
        else:
            if Lr is None or lv < Lr:
                Lr = lv

    return Ls, Lr
