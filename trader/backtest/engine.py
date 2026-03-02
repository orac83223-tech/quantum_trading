"""engine.py — 백테스트 이벤트 루프

핵심 원칙:
  - 진입: t+1 시가(Open[t+1])
  - 갭 처리: 다음날 시가가 SL 아래면 해당 시가에서 즉시 청산
  - 비용: 왕복 거래비용 + 슬리피지 반영
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from trader.config import AppConfig, get_config
from trader.indicators.atr import atr
from trader.strategy.qg_confluence_v1 import Signal, compute_signals
from trader.strategy.ev_gate import compute_ev_gate
from trader.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Trade:
    """완료된 하나의 트레이드."""
    ticker: str
    entry_date: object
    entry_price: float
    exit_date: object
    exit_price: float
    sl: float
    tp1: float
    Ls: float
    Lr: float
    size: int                       # 수량
    pnl: float = 0.0               # 손익 (비용 차감 후)
    pnl_r: float = 0.0             # R 배수 손익
    exit_reason: str = ""          # sl / tp1 / trailing / time_stop / gap
    score: int = 0
    reasons: List[str] = field(default_factory=list)


@dataclass
class OpenPosition:
    """현재 보유 중인 포지션."""
    ticker: str
    entry_date: object
    entry_price: float
    size: int
    sl: float                      # 현재 손절가 (트레일링 반영)
    tp1: float
    Ls: float
    Lr: float
    bars_held: int = 0
    tp1_hit: bool = False          # TP1 도달 여부
    remaining_ratio: float = 1.0   # 잔여 비율 (TP1 청산 후)
    signal: Optional[Signal] = None


class BacktestEngine:
    """Quantum–Gann Confluence v1 백테스트 엔진."""

    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or get_config()
        self.initial_equity: float = 100_000_000  # 1억 원
        self.equity: float = self.initial_equity
        self.equity_curve: List[Tuple[object, float]] = []
        self.trades: List[Trade] = []
        self.open_positions: Dict[str, OpenPosition] = {}
        self.daily_r_loss: float = 0.0

    def run(
        self,
        ticker: str,
        df: pd.DataFrame,
    ) -> List[Trade]:
        """단일 종목에 대해 백테스트를 실행한다.

        Args:
            ticker: 종목 코드
            df: OHLCV DataFrame

        Returns:
            완료된 Trade 리스트
        """
        sc = self.cfg.strategy
        rc = self.cfg.risk

        signals = compute_signals(ticker, df, self.cfg)
        signal_map: Dict[int, Signal] = {s.signal_iloc: s for s in signals}

        trades: List[Trade] = []

        for i in range(len(df)):
            current_date = df.index[i]

            # ── 보유 포지션 관리 ──────────────────────
            closed = self._manage_positions(df, i, trades)

            # ── 일일 손실 한도 확인 ───────────────────
            if self.daily_r_loss >= rc.daily_stop_R:
                continue

            # ── 최대 포지션 수 확인 ───────────────────
            if len(self.open_positions) >= rc.max_positions:
                continue

            # ── 신호 확인 (t일에 신호, t+1 진입) ──────
            # signal_iloc 은 신호 발생일, 진입은 t+1 = i
            signal_iloc = i - 1
            if signal_iloc not in signal_map:
                continue

            sig = signal_map[signal_iloc]

            # 이미 같은 종목 보유 중이면 스킵
            if ticker in self.open_positions:
                continue

            # EV Gate
            if self.cfg.ev_gate.enabled:
                ev = compute_ev_gate(sig.entry_price_est, sig.sl, sig.tp1)
                if not ev.passed:
                    continue

            # ── 포지션 사이징 ─────────────────────────
            R = sig.entry_price_est - sig.sl
            if R <= 0:
                continue

            size = int((self.equity * rc.risk_pct_per_trade) / R)
            if size <= 0:
                continue

            # Gann penalty
            size = int(size * sig.gann_penalty)
            if size <= 0:
                continue

            # 진입가 = Open[t+1] (= 현재 바의 시가, i가 t+1에 해당)
            entry_price = df["Open"].iloc[i]

            # 슬리피지
            entry_price = entry_price * (1 + rc.slippage)

            # 갭 처리: 시가가 이미 SL 아래면 진입 스킵
            if entry_price <= sig.sl:
                continue

            pos = OpenPosition(
                ticker=ticker,
                entry_date=current_date,
                entry_price=entry_price,
                size=size,
                sl=sig.sl,
                tp1=sig.tp1,
                Ls=sig.Ls,
                Lr=sig.Lr,
                signal=sig,
            )
            self.open_positions[ticker] = pos

            # 자본 차감 (매수 비용)
            cost = entry_price * size * (rc.cost_roundtrip / 2)
            self.equity -= cost

            # ── 에쿼티 기록 ───────────────────────────
            self.equity_curve.append((current_date, self.equity))

        # 남은 포지션 강제 청산
        if self.open_positions:
            last_idx = len(df) - 1
            remaining = list(self.open_positions.keys())
            for tk in remaining:
                self._close_position(
                    tk, df, last_idx, "end_of_data", trades
                )

        self.trades.extend(trades)
        return trades

    def _manage_positions(
        self,
        df: pd.DataFrame,
        current_idx: int,
        trades: List[Trade],
    ) -> List[str]:
        """보유 포지션의 SL/TP/Trailing/TimeStop 을 관리한다."""
        sc = self.cfg.strategy
        rc = self.cfg.risk
        closed: List[str] = []

        for ticker in list(self.open_positions.keys()):
            pos = self.open_positions[ticker]
            pos.bars_held += 1

            open_price = df["Open"].iloc[current_idx]
            high = df["High"].iloc[current_idx]
            low = df["Low"].iloc[current_idx]
            close = df["Close"].iloc[current_idx]

            # ── 갭 다운 SL ────────────────────────────
            if open_price <= pos.sl:
                self._close_position(ticker, df, current_idx, "gap_sl", trades, exit_price=open_price)
                closed.append(ticker)
                continue

            # ── 장중 SL 체크 ──────────────────────────
            if low <= pos.sl:
                self._close_position(ticker, df, current_idx, "sl", trades, exit_price=pos.sl)
                closed.append(ticker)
                continue

            # ── TP1 체크 ──────────────────────────────
            if not pos.tp1_hit and high >= pos.tp1:
                pos.tp1_hit = True
                # TP1 도달: tp1_ratio 만큼 부분 청산
                partial_size = int(pos.size * sc.tp1_ratio)
                if partial_size > 0:
                    pnl = (pos.tp1 - pos.entry_price) * partial_size
                    cost = pos.tp1 * partial_size * (rc.cost_roundtrip / 2)
                    self.equity += pnl - cost

                    pos.size -= partial_size
                    pos.remaining_ratio = 1.0 - sc.tp1_ratio

                    # 트레일링 SL 이동
                    atr_series = atr(df, period=self.cfg.indicators.atr_period)
                    current_atr = atr_series.iloc[current_idx]
                    if not np.isnan(current_atr):
                        band = self.cfg.indicators.band_atr_mult * current_atr
                        pos.sl = pos.Lr - band

                if pos.size <= 0:
                    self.open_positions.pop(ticker, None)
                    closed.append(ticker)
                    # 완료 트레이드 기록
                    R = pos.entry_price - (pos.signal.sl if pos.signal else pos.sl)
                    trades.append(Trade(
                        ticker=ticker,
                        entry_date=pos.entry_date,
                        entry_price=pos.entry_price,
                        exit_date=df.index[current_idx],
                        exit_price=pos.tp1,
                        sl=pos.signal.sl if pos.signal else pos.sl,
                        tp1=pos.tp1,
                        Ls=pos.Ls,
                        Lr=pos.Lr,
                        size=int(pos.size + partial_size),
                        pnl=pnl - cost,
                        pnl_r=(pnl - cost) / R if R > 0 else 0,
                        exit_reason="tp1",
                        score=pos.signal.score if pos.signal else 0,
                        reasons=pos.signal.reasons if pos.signal else [],
                    ))
                    continue

            # ── 트레일링 SL (TP1 이후) ────────────────
            if pos.tp1_hit and close > pos.Lr:
                atr_series = atr(df, period=self.cfg.indicators.atr_period)
                current_atr = atr_series.iloc[current_idx]
                if not np.isnan(current_atr):
                    band = self.cfg.indicators.band_atr_mult * current_atr
                    new_sl = pos.Lr - band
                    if new_sl > pos.sl:
                        pos.sl = new_sl

            # ── 시간 정지 ─────────────────────────────
            if pos.bars_held >= sc.time_stop_bars and not pos.tp1_hit:
                self._close_position(ticker, df, current_idx, "time_stop", trades)
                closed.append(ticker)
                continue

        return closed

    def _close_position(
        self,
        ticker: str,
        df: pd.DataFrame,
        current_idx: int,
        reason: str,
        trades: List[Trade],
        exit_price: Optional[float] = None,
    ) -> None:
        """포지션을 청산하고 Trade 를 기록한다."""
        rc = self.cfg.risk
        pos = self.open_positions.pop(ticker, None)
        if pos is None:
            return

        if exit_price is None:
            exit_price = df["Close"].iloc[current_idx]

        # 슬리피지 (매도)
        exit_price = exit_price * (1 - rc.slippage)

        pnl = (exit_price - pos.entry_price) * pos.size
        cost = exit_price * pos.size * (rc.cost_roundtrip / 2)
        net_pnl = pnl - cost

        self.equity += net_pnl + pos.entry_price * pos.size  # 원금 + 손익

        R = pos.entry_price - (pos.signal.sl if pos.signal else pos.sl)
        pnl_r = net_pnl / R if R > 0 else 0

        if pnl_r < 0:
            self.daily_r_loss += abs(pnl_r)

        trades.append(Trade(
            ticker=ticker,
            entry_date=pos.entry_date,
            entry_price=pos.entry_price,
            exit_date=df.index[current_idx],
            exit_price=exit_price,
            sl=pos.signal.sl if pos.signal else pos.sl,
            tp1=pos.tp1,
            Ls=pos.Ls,
            Lr=pos.Lr,
            size=pos.size,
            pnl=round(net_pnl, 2),
            pnl_r=round(pnl_r, 4),
            exit_reason=reason,
            score=pos.signal.score if pos.signal else 0,
            reasons=pos.signal.reasons if pos.signal else [],
        ))


def run_backtest(
    ticker_data: Dict[str, pd.DataFrame],
    cfg: Optional[AppConfig] = None,
) -> Tuple[List[Trade], List[Tuple[object, float]]]:
    """다중 종목 백테스트를 실행한다.

    Args:
        ticker_data: {티커: OHLCV DataFrame}
        cfg: 설정

    Returns:
        (trades, equity_curve)
    """
    if cfg is None:
        cfg = get_config()

    engine = BacktestEngine(cfg)

    for ticker, df in ticker_data.items():
        log.info("백테스트 실행: %s (%d bars)", ticker, len(df))
        engine.run(ticker, df)

    log.info("백테스트 완료: 총 %d 트레이드", len(engine.trades))
    return engine.trades, engine.equity_curve
