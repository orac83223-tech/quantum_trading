"""test_ev_gate.py — EV gate 통과/실패 케이스 검증"""

import pytest

from trader.strategy.ev_gate import compute_ev_gate, EvResult


class TestEvGate:
    """EV Gate 통과/실패 케이스 검증."""

    def test_positive_ev_passes(self):
        """R:G 비율이 좋고 성공률이 높으면 통과."""
        result = compute_ev_gate(
            entry_price=1000,
            sl=900,           # R = 100
            tp1=1300,         # G = 300
            historical_win_rate=0.6,
        )
        # EV = 0.6 * 300 - 0.4 * 100 - 5 = 180 - 40 - 5 = 135 > 0
        assert result.passed is True
        assert result.R == 100
        assert result.G == 300
        assert result.ev > 0

    def test_negative_ev_fails(self):
        """R:G 비율이 나쁘면 실패."""
        result = compute_ev_gate(
            entry_price=1000,
            sl=800,           # R = 200
            tp1=1050,         # G = 50
            historical_win_rate=0.3,
        )
        # EV = 0.3 * 50 - 0.7 * 200 - 5 = 15 - 140 - 5 = -130 < 0
        assert result.passed is False
        assert result.ev < 0

    def test_borderline_with_cost(self):
        """비용 버퍼를 포함하면 경계에서 실패할 수 있다."""
        result = compute_ev_gate(
            entry_price=10000,
            sl=9500,          # R = 500
            tp1=11000,        # G = 1000
            historical_win_rate=0.4,
        )
        # cost = 0.005 * 10000 = 50
        # EV = 0.4 * 1000 - 0.6 * 500 - 50 = 400 - 300 - 50 = 50 > 0
        assert result.passed is True
        assert result.cost_buffer == 50.0

    def test_zero_win_rate(self):
        """성공률 0이면 무조건 실패."""
        result = compute_ev_gate(
            entry_price=1000,
            sl=900,
            tp1=1200,
            historical_win_rate=0.0,
        )
        assert result.passed is False

    def test_high_win_rate(self):
        """성공률 90%면 대부분 통과."""
        result = compute_ev_gate(
            entry_price=1000,
            sl=950,
            tp1=1020,
            historical_win_rate=0.9,
        )
        # R=50, G=20, cost=5
        # EV = 0.9*20 - 0.1*50 - 5 = 18 - 5 - 5 = 8 > 0
        assert result.passed is True

    def test_default_win_rate_estimation(self):
        """historical_win_rate=None 이면 R:G 기반 기본값 사용."""
        result = compute_ev_gate(
            entry_price=1000,
            sl=900,
            tp1=1200,
            historical_win_rate=None,
        )
        # 기본 p = (R+cost)/(G+R) + 0.05
        assert result.p > 0
        assert result.p <= 0.95
