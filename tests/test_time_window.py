"""test_time_window.py — time_ok 계산 검증"""

import pytest


def time_ok(bars_since_pivot: int, time_bars=None, time_window: int = 5) -> bool:
    """time_ok 판별 로직 (독립 함수로 추출하여 테스트)."""
    if time_bars is None:
        time_bars = [45, 90, 135, 180, 270, 360]
    return any(abs(bars_since_pivot - ti) <= time_window for ti in time_bars)


class TestTimeWindow:
    """time_ok 범위 계산 검증."""

    def test_exact_match(self):
        """정확히 time_bar 에 해당하면 True."""
        assert time_ok(45) is True
        assert time_ok(90) is True
        assert time_ok(180) is True
        assert time_ok(360) is True

    def test_within_window(self):
        """time_window 이내면 True."""
        # 45 ± 5
        assert time_ok(40) is True
        assert time_ok(50) is True
        # 90 ± 5
        assert time_ok(85) is True
        assert time_ok(95) is True

    def test_outside_window(self):
        """time_window 밖이면 False."""
        assert time_ok(39) is False   # 45-6
        assert time_ok(51) is False   # 45+6
        assert time_ok(60) is False   # 45와 90 사이
        assert time_ok(100) is False  # 90+10

    def test_custom_window(self):
        """사용자 지정 time_window 테스트."""
        assert time_ok(42, time_window=3) is True   # 45-3=42
        assert time_ok(41, time_window=3) is False  # 45-4

    def test_zero_bars(self):
        """0 bars 는 어떤 time_bar 에도 해당 안 됨."""
        assert time_ok(0) is False

    def test_custom_time_bars(self):
        """사용자 지정 time_bars."""
        custom = [30, 60]
        assert time_ok(30, time_bars=custom) is True
        assert time_ok(35, time_bars=custom) is True  # 30+5
        assert time_ok(45, time_bars=custom) is False  # 30+15, 60-15

    def test_boundary_exact(self):
        """경계값 정확히 time_window 거리."""
        assert time_ok(40, time_window=5) is True   # |40-45| = 5 <= 5
        assert time_ok(39, time_window=5) is False  # |39-45| = 6 > 5
