"""qg_confluence_v1.py — Quantum–Gann Confluence v1 메인 신호 생성"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from trader.config import AppConfig, get_config
from trader.indicators.atr import atr
from trader.indicators.gann_angle import compute_gann_slope, gann_1x1_line, is_trend_ok
from trader.indicators.pivots import get_latest_confirmed_pivot
from trader.indicators.so9 import find_support_resistance
from trader.indicators.qpl import find_nearest_qpl
from trader.utils.math import sma
from trader.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Signal:
    """하나의 매수 신호를 나타낸다."""
    ticker: str
    signal_date: object          # 신호 발생일 (index)
    signal_iloc: int             # 신호 발생 iloc
    entry_price_est: float       # 예상 진입가 (다음날 시가 추정)
    sl: float                    # 초기 손절가
    tp1: float                   # 목표가 1
    Ls: float                    # So9 지지선
    Lr: float                    # So9 저항선
    score: int                   # 신호 스코어
    reasons: List[str] = field(default_factory=list)
    trend_ok: bool = True
    gann_penalty: float = 1.0    # trend_ok False 시 0.5


def compute_signals(
    ticker: str,
    df: pd.DataFrame,
    cfg: Optional[AppConfig] = None,
) -> List[Signal]:
    """주어진 OHLCV 데이터에서 Quantum–Gann Confluence v1 매수 신호를 생성한다.

    핵심 원칙:
      - 모든 계산은 t일 데이터까지만 사용
      - Pivot Low 는 t+3 확정 후에만 사용
      - 진입은 t+1 시가 (백테스트 시 Open[t+1])
    """
    if cfg is None:
        cfg = get_config()

    ic = cfg.indicators
    sc = cfg.strategy

    if len(df) < max(200, ic.gann_scale_n + ic.pivot_bars * 2 + 20):
        return []

    # ── 사전 계산 ──────────────────────────────────────────
    atr_series = atr(df, period=ic.atr_period)
    band_series = ic.band_atr_mult * atr_series

    sma5 = sma(df["Close"], 5)
    sma50 = sma(df["Close"], 50)
    sma200 = sma(df["Close"], 200)

    atr_pct_series = atr_series / df["Close"]
    
    signals: List[Signal] = []

    # ── 바 순회 ────────────────────────────────────────────
    # 최소 시작 위치: sma200 이 유효해지는 시점
    start_idx = 200

    for i in range(start_idx, len(df) - 1):  # -1: t+1 진입가 필요
        # ATR 유효성
        current_atr = atr_series.iloc[i]
        if np.isnan(current_atr) or current_atr <= 0:
            continue

        band = band_series.iloc[i]

        # ── 피벗 로우 앵커 ──────────────────────────────
        pivot = get_latest_confirmed_pivot(df, i, left=ic.pivot_bars, right=ic.pivot_bars)
        if pivot is None:
            continue

        pivot_iloc, pivot_price, pivot_date = pivot

        # ── So9 레벨 ───────────────────────────────────
        Ls, Lr = find_support_resistance(
            df["Close"].iloc[i],
            pivot_price,
            angles=ic.so9_angles,
            k_cycles=ic.so9_k_cycles,
        )
        if Ls is None or Lr is None:
            continue

        # ── 신호 스코어 ────────────────────────────────
        score = 0
        reasons: List[str] = []

        # 1) price_touch: Low[t] <= Ls + band
        low_t = df["Low"].iloc[i]
        if low_t <= Ls + band:
            score += 1
            reasons.append("price_touch")

        # 2) time_ok: 시간 공명
        bars_since_pivot = i - pivot_iloc
        time_ok = any(
            abs(bars_since_pivot - ti) <= ic.time_window
            for ti in ic.time_bars
        )
        if time_ok:
            score += 1
            reasons.append("time_ok")

        # 3) QPL confluence (v2)
        if sc.use_qpl_confluence:
            # 피벗 시점의 변동성 참조
            pivot_vol = atr_pct_series.iloc[pivot_iloc] if not np.isnan(atr_pct_series.iloc[pivot_iloc]) else 0.02
            ls_qpl, lr_qpl = find_nearest_qpl(df["Close"].iloc[i], pivot_price, pivot_vol)
            
            if ls_qpl is not None and (df["Low"].iloc[i] <= ls_qpl + band):
                score += 1
                reasons.append("qpl")

        # ── 스코어 임계값 ──────────────────────────────
        if score < sc.score_threshold:
            continue

        # ── Rejection 확인 ─────────────────────────────
        close_t = df["Close"].iloc[i]
        rejection = (low_t <= Ls + band) and (close_t >= Ls + 0.5 * band)
        if not rejection:
            continue

        # ── Confirmation ───────────────────────────────
        confirmed = False
        if sc.confirmation == "sma5":
            if not np.isnan(sma5.iloc[i]):
                confirmed = close_t >= sma5.iloc[i]
        elif sc.confirmation == "prev_high":
            if i > 0:
                confirmed = close_t > df["High"].iloc[i - 1]

        if not confirmed:
            continue

        # ── Trend Filter ───────────────────────────────
        trend_pass = True
        if sc.trend_filter == "sma200":
            if not np.isnan(sma200.iloc[i]):
                trend_pass = close_t >= sma200.iloc[i]
        elif sc.trend_filter == "sma50":
            if not np.isnan(sma50.iloc[i]):
                trend_pass = close_t >= sma50.iloc[i]
        # trend_filter == "none" → 항상 통과

        if not trend_pass:
            continue

        # ── Gann 1×1 트렌드 ───────────────────────────
        trend_ok_gann = is_trend_ok(df, i, pivot_price, pivot_iloc, ic.gann_scale_n)
        gann_penalty = 1.0 if trend_ok_gann else ic.gann_penalty_fraction

        # ── 진입가 / SL / TP1 ─────────────────────────
        entry_price_est = df["Open"].iloc[i + 1]
        sl = Ls - sc.sl_atr_mult * current_atr
        tp1 = Lr

        # SL 이 0 이하면 스킵
        if sl <= 0 or entry_price_est <= sl:
            continue

        signals.append(Signal(
            ticker=ticker,
            signal_date=df.index[i],
            signal_iloc=i,
            entry_price_est=entry_price_est,
            sl=round(sl, 2),
            tp1=round(tp1, 2),
            Ls=round(Ls, 2),
            Lr=round(Lr, 2),
            score=score,
            reasons=reasons,
            trend_ok=trend_ok_gann,
            gann_penalty=gann_penalty,
        ))

    log.info("%s: %d 신호 생성 (전체 %d bars)", ticker, len(signals), len(df))
    return signals
