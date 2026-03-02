"""test_so9.py — Square of 9 레벨 계산 검증"""

import math
import pytest

from trader.indicators.so9 import compute_so9_levels, find_support_resistance


class TestComputeSo9Levels:
    """So9 레벨 계산 정확성 검증."""

    def test_known_anchor(self):
        """알려진 앵커 가격에서 레벨이 올바르게 계산되는지 확인."""
        # P0 = 100 → r = 10
        levels = compute_so9_levels(100.0, angles=[90, 180, 360], k_cycles=[0])

        r = math.sqrt(100)  # = 10.0
        expected = set()
        for angle in [90, 180, 360]:
            delta = angle / 360.0
            upper = (r + delta) ** 2
            lower_val = r - delta
            lower = lower_val ** 2 if lower_val > 0 else 0.0
            if upper > 0:
                expected.add(round(upper, 2))
            if lower > 0:
                expected.add(round(lower, 2))

        assert set(levels) == expected

    def test_levels_are_sorted(self):
        """레벨이 오름차순 정렬되어야 한다."""
        levels = compute_so9_levels(500.0)
        assert levels == sorted(levels)

    def test_all_positive(self):
        """모든 레벨이 양수여야 한다."""
        levels = compute_so9_levels(50.0)
        assert all(lv > 0 for lv in levels)

    def test_multiple_cycles(self):
        """k=0, k=1 에서 다른 레벨이 생성되어야 한다."""
        levels_k0 = compute_so9_levels(100.0, k_cycles=[0])
        levels_k01 = compute_so9_levels(100.0, k_cycles=[0, 1])
        assert len(levels_k01) > len(levels_k0)

    def test_small_price(self):
        """소수점 가격에서도 정상 동작."""
        levels = compute_so9_levels(4.0, angles=[90], k_cycles=[0])
        r = math.sqrt(4.0)  # = 2.0
        delta = 90 / 360.0  # = 0.25
        expected_upper = round((r + delta) ** 2, 2)  # (2.25)^2 = 5.0625
        expected_lower = round((r - delta) ** 2, 2)  # (1.75)^2 = 3.0625
        assert expected_upper in levels
        assert expected_lower in levels


class TestFindSupportResistance:
    """지지/저항 레벨 검색 검증."""

    def test_basic_sr(self):
        """현재가 기준 가장 가까운 지지/저항 반환."""
        Ls, Lr = find_support_resistance(
            current_price=105.0,
            anchor_price=100.0,
            angles=[90, 180, 360],
            k_cycles=[0],
        )
        assert Ls is not None
        assert Lr is not None
        assert Ls <= 105.0
        assert Lr > 105.0

    def test_support_below_resistance_above(self):
        """Ls < current_price < Lr 관계."""
        Ls, Lr = find_support_resistance(
            current_price=500.0,
            anchor_price=480.0,
        )
        if Ls is not None:
            assert Ls <= 500.0
        if Lr is not None:
            assert Lr > 500.0
