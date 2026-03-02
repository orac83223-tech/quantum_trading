"""metrics.py — 승률/PF/MDD/CAGR/avgR 산출"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

import numpy as np


@dataclass
class BacktestMetrics:
    """백테스트 결과 지표."""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pnl: float = 0.0
    avg_pnl: float = 0.0
    avg_r: float = 0.0
    max_drawdown_pct: float = 0.0
    cagr_pct: float = 0.0
    trades_per_year: float = 0.0
    best_trade_r: float = 0.0
    worst_trade_r: float = 0.0
    avg_bars_held: float = 0.0


def compute_metrics(
    trades: list,
    equity_curve: List[Tuple[object, float]],
    initial_equity: float = 100_000_000,
    years: float = 1.0,
) -> BacktestMetrics:
    """트레이드 리스트에서 백테스트 지표를 산출한다."""
    m = BacktestMetrics()

    if not trades:
        return m

    m.total_trades = len(trades)
    m.winning_trades = sum(1 for t in trades if t.pnl > 0)
    m.losing_trades = sum(1 for t in trades if t.pnl <= 0)
    m.win_rate = m.winning_trades / m.total_trades if m.total_trades > 0 else 0.0

    # Profit Factor
    gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
    gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
    m.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    # PnL
    m.total_pnl = sum(t.pnl for t in trades)
    m.avg_pnl = m.total_pnl / m.total_trades

    # R-multiple
    r_values = [t.pnl_r for t in trades]
    m.avg_r = np.mean(r_values) if r_values else 0.0
    m.best_trade_r = max(r_values) if r_values else 0.0
    m.worst_trade_r = min(r_values) if r_values else 0.0

    # Max Drawdown
    if equity_curve:
        equities = [e[1] for e in equity_curve]
        m.max_drawdown_pct = _max_drawdown(equities)

    # CAGR
    if equity_curve and years > 0:
        final_equity = equity_curve[-1][1] if equity_curve else initial_equity
        m.cagr_pct = ((final_equity / initial_equity) ** (1 / years) - 1) * 100

    # Trades per year
    m.trades_per_year = m.total_trades / years if years > 0 else 0.0

    return m


def _max_drawdown(equities: List[float]) -> float:
    """에쿼티 시리즈에서 최대 낙폭(%)을 계산한다."""
    if not equities:
        return 0.0

    peak = equities[0]
    max_dd = 0.0

    for eq in equities:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    return round(max_dd * 100, 2)


def format_metrics(m: BacktestMetrics, start: str = "", end: str = "") -> str:
    """메트릭스를 사람이 읽기 좋은 문자열로 포맷한다."""
    lines = [
        f"=== Quantum–Gann Confluence v1 Backtest ({start} ~ {end}) ===",
        "",
        f"Total Trades   : {m.total_trades}",
        f"Win Rate       : {m.win_rate*100:.1f}%",
        f"Profit Factor  : {m.profit_factor:.2f}",
        f"CAGR           : {m.cagr_pct:.1f}%",
        f"Max Drawdown   : -{m.max_drawdown_pct:.1f}%",
        f"Avg R          : {m.avg_r:.2f}R",
        f"Best Trade     : {m.best_trade_r:.2f}R",
        f"Worst Trade    : {m.worst_trade_r:.2f}R",
        f"Trades / Year  : {m.trades_per_year:.1f}",
        f"Total PnL      : {m.total_pnl:,.0f} KRW",
    ]
    return "\n".join(lines)
