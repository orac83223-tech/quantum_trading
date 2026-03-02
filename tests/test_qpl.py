"""test_qpl.py — QPL 지표 테스트"""

import math
from trader.indicators.qpl import compute_qpl_levels, find_nearest_qpl

class TestQPL:
    def test_compute_levels(self):
        anchor = 100.0
        vol = 0.05
        n = 3
        levels = compute_qpl_levels(anchor, vol, n)
        
        assert len(levels) == 7 # anchor + 3 up + 3 down
        assert anchor in levels
        
        up1 = round(100.0 * math.exp(0.05), 2)
        down1 = round(100.0 * math.exp(-0.05), 2)
        
        assert up1 in levels
        assert down1 in levels
        
        # 정렬 확인
        assert levels == sorted(levels)
        
    def test_find_nearest(self):
        anchor = 100.0
        vol = 0.05
        
        ls, lr = find_nearest_qpl(102.0, anchor, vol, n_levels=3)
        assert ls is not None
        assert lr is not None
        assert ls <= 102.0
        assert lr > 102.0
        
        # 100.0 이 지지선, 105.13 이 저항선이 됨
        assert ls == 100.0
        assert lr == round(100.0 * math.exp(0.05), 2)
