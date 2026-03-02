"""test_pivots.py — Pivot Low look-ahead 방지 검증"""

import numpy as np
import pandas as pd
import pytest

from trader.indicators.pivots import (
    detect_pivot_lows,
    confirmed_pivot_lows,
    get_latest_confirmed_pivot,
)


def _make_df(lows):
    """테스트용 간단 OHLCV DataFrame 생성."""
    n = len(lows)
    df = pd.DataFrame({
        "Open": lows,
        "High": [l + 10 for l in lows],
        "Low": lows,
        "Close": [l + 5 for l in lows],
        "Volume": [1000] * n,
    }, index=pd.date_range("2024-01-01", periods=n, freq="B"))
    return df


class TestDetectPivotLows:
    """detect_pivot_lows 기본 동작 검증."""

    def test_single_pivot(self):
        # index 5 가 최저 (양쪽 3 bars 내에서)
        lows = [100, 95, 90, 85, 82, 80, 82, 85, 90, 95, 100]
        series = pd.Series(lows)
        pivots = detect_pivot_lows(series, left=3, right=3)
        assert pivots.iloc[5]

    def test_no_pivot_at_edges(self):
        """양 끝에서는 피벗이 감지되지 않아야 한다."""
        lows = [70, 80, 90, 100, 110, 120, 130]
        series = pd.Series(lows)
        pivots = detect_pivot_lows(series, left=3, right=3)
        # index 0, 1, 2 는 왼쪽 bars 부족
        assert not pivots.iloc[0]
        assert not pivots.iloc[1]
        assert not pivots.iloc[2]

    def test_multiple_pivots(self):
        lows = [100, 95, 90, 85, 80, 85, 90, 95, 90, 85, 78, 85, 90, 95, 100]
        series = pd.Series(lows)
        pivots = detect_pivot_lows(series, left=3, right=3)
        pivot_indices = [i for i, v in enumerate(pivots) if v]
        assert 4 in pivot_indices   # 80 at index 4
        assert 10 in pivot_indices  # 78 at index 10


class TestConfirmedPivotLows:
    """confirmed_pivot_lows — t+3 확정 지연 검증."""

    def test_confirmation_delayed(self):
        """피벗이 i에서 발생하면 i+3에서 확정되어야 한다."""
        lows = [100, 95, 90, 85, 80, 85, 90, 95, 100, 105, 110]
        series = pd.Series(lows)
        confirmed = confirmed_pivot_lows(series, left=3, right=3)

        # 피벗은 index 4 (값 80) → 확정은 index 7 (4+3)
        assert not confirmed.iloc[4]  # 발생 시점에서는 미확정
        assert not confirmed.iloc[5]
        assert not confirmed.iloc[6]
        assert confirmed.iloc[7]      # t+3 에서 확정


class TestGetLatestConfirmedPivot:
    """get_latest_confirmed_pivot — look-ahead 방지 핵심 테스트."""

    def test_no_future_pivot_used(self):
        """현재 바보다 미래에 있는 피벗은 절대 사용 불가."""
        lows = [100, 95, 90, 85, 80, 85, 90, 95, 90, 85, 78, 85, 90, 95, 100]
        df = _make_df(lows)

        # current_idx = 6 → 사용 가능 피벗: i=4 - right=3 이므로 확정 필요
        # i=4 가 피벗, current >= 4+3=7 이어야 사용 가능
        result = get_latest_confirmed_pivot(df, current_idx=6, left=3, right=3)
        assert result is None  # 아직 확정 안 됨

        result = get_latest_confirmed_pivot(df, current_idx=7, left=3, right=3)
        assert result is not None
        assert result[0] == 4   # pivot_iloc
        assert result[1] == 80  # pivot_price

    def test_returns_most_recent_pivot(self):
        """여러 피벗 중 가장 최근 확정 피벗을 반환해야 한다."""
        lows = [100, 95, 90, 85, 80, 85, 90, 95, 90, 85, 78, 85, 90, 95, 100]
        df = _make_df(lows)

        # current_idx=13: 두 피벗 모두 확정 가능 (4+3=7 ≤ 13, 10+3=13 ≤ 13)
        result = get_latest_confirmed_pivot(df, current_idx=13, left=3, right=3)
        assert result is not None
        assert result[0] == 10  # 더 최근 피벗
        assert result[1] == 78

    def test_no_pivot_with_insufficient_data(self):
        """데이터가 부족하면 None 반환."""
        lows = [100, 95, 90]
        df = _make_df(lows)
        result = get_latest_confirmed_pivot(df, current_idx=2, left=3, right=3)
        assert result is None
