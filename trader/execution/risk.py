"""risk.py — 포지션 사이징 + 일일 손실 한도"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from trader.config import AppConfig, get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class PositionSize:
    """포지션 사이징 결과."""
    shares: int
    risk_per_share: float
    total_risk: float
    position_value: float


def calculate_position_size(
    equity: float,
    entry_price: float,
    sl_price: float,
    gann_penalty: float = 1.0,
    cfg: Optional[AppConfig] = None,
) -> PositionSize:
    """포지션 사이즈를 계산한다.

    size = (equity * risk_pct_per_trade) / R
    R = entry_price - sl_price

    Args:
        equity: 현재 자본금
        entry_price: 예상 진입가
        sl_price: 손절가
        gann_penalty: Gann 트렌드 반영 비율 (1.0 또는 0.5)
        cfg: 설정

    Returns:
        PositionSize
    """
    if cfg is None:
        cfg = get_config()

    rc = cfg.risk

    R = entry_price - sl_price
    if R <= 0:
        return PositionSize(shares=0, risk_per_share=0, total_risk=0, position_value=0)

    raw_size = (equity * rc.risk_pct_per_trade) / R
    adjusted_size = int(raw_size * gann_penalty)

    if adjusted_size <= 0:
        return PositionSize(shares=0, risk_per_share=R, total_risk=0, position_value=0)

    total_risk = R * adjusted_size
    position_value = entry_price * adjusted_size

    return PositionSize(
        shares=adjusted_size,
        risk_per_share=round(R, 2),
        total_risk=round(total_risk, 2),
        position_value=round(position_value, 2),
    )


class DailyRiskManager:
    """일일 손실 한도를 관리한다."""

    def __init__(self, cfg: Optional[AppConfig] = None):
        if cfg is None:
            cfg = get_config()
        self.max_daily_r = cfg.risk.daily_stop_R
        self.daily_r_loss: float = 0.0

    def can_trade(self) -> bool:
        """추가 진입이 가능한지 확인."""
        return self.daily_r_loss < self.max_daily_r

    def record_loss(self, r_loss: float) -> None:
        """손실을 R 배수로 기록한다."""
        if r_loss > 0:
            self.daily_r_loss += r_loss
            log.info("일일 R 손실 누적: %.2fR (한도: %dR)", self.daily_r_loss, self.max_daily_r)

    def reset(self) -> None:
        """일일 카운터를 초기화한다."""
        self.daily_r_loss = 0.0
