"""ev_gate.py — Expected Value 필터

EV Gate:
  R = entry_price - SL
  G = TP1_price - entry_price
  p = 유사 이벤트 기반 성공률 추정
  gate_pass = (p * G) > ((1 - p) * R + COST_BUFFER)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from trader.config import AppConfig, get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class EvResult:
    """EV Gate 판정 결과."""
    passed: bool
    p: float           # 추정 성공률
    G: float           # 기대 보상
    R: float           # 리스크
    ev: float           # p * G - (1-p) * R - cost
    cost_buffer: float


def compute_ev_gate(
    entry_price: float,
    sl: float,
    tp1: float,
    historical_win_rate: Optional[float] = None,
    cfg: Optional[AppConfig] = None,
) -> EvResult:
    """EV Gate 를 계산한다.

    Args:
        entry_price: 진입 예상가
        sl: 손절가
        tp1: 목표가 1
        historical_win_rate: 과거 유사 신호 성공률 (None 이면 기본값 사용)
        cfg: 설정

    Returns:
        EvResult
    """
    if cfg is None:
        cfg = get_config()

    ec = cfg.ev_gate

    R = entry_price - sl
    G = tp1 - entry_price
    cost_buffer = ec.cost_buffer_pct * entry_price

    # 성공률 추정
    if historical_win_rate is not None:
        p = historical_win_rate
    else:
        # 기본값: R:G 비율 기반 최소 필요 승률에 5% 마진
        if G + R > 0:
            min_p = (R + cost_buffer) / (G + R)
            p = min(min_p + 0.05, 0.95)
        else:
            p = 0.0

    ev = p * G - (1 - p) * R - cost_buffer
    passed = ev > 0

    return EvResult(
        passed=passed,
        p=round(p, 4),
        G=round(G, 2),
        R=round(R, 2),
        ev=round(ev, 2),
        cost_buffer=round(cost_buffer, 2),
    )


def estimate_win_rate(
    signals_history: list,
    ticker: str,
    min_score: int = 2,
    lookback_bars: int = 700,
) -> Optional[float]:
    """과거 유사 신호의 성공률을 추정한다.

    성공 = 진입 후 success_bars(45) 이내에 TP1 도달

    Args:
        signals_history: 과거 신호 + 결과 리스트
        ticker: 대상 종목
        min_score: 최소 스코어
        lookback_bars: 최대 과거 참조 바

    Returns:
        성공률 (0~1). 데이터 부족 시 None.
    """
    # 같은 종목, score >= min_score 인 신호만 필터
    relevant = [
        s for s in signals_history
        if s.get("ticker") == ticker and s.get("score", 0) >= min_score
    ]

    if len(relevant) < 5:
        return None  # 데이터 부족

    successes = sum(1 for s in relevant if s.get("hit_tp1", False))
    return successes / len(relevant)
