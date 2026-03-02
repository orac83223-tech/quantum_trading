"""test_reporting_smoke.py — 리포트 생성 스모크 테스트"""

import shutil
from pathlib import Path
import pandas as pd
from datetime import datetime

from trader.config import AppConfig
from trader.backtest.metrics import BacktestMetrics
from trader.backtest.report import generate_report

def test_generate_report_smoke(tmp_path):
    # 더미 데이터 생성
    trades = []
    equity_curve = [
        (datetime(2025, 1, 1), 100000000.0),
        (datetime(2025, 1, 2), 101000000.0),
        (datetime(2025, 1, 3), 99000000.0),
        (datetime(2025, 1, 4), 102000000.0)
    ]
    metrics = BacktestMetrics(
        total_trades=0, win_rate=0.0, profit_factor=0.0, 
        cagr_pct=2.0, max_drawdown_pct=1.0, avg_r=0.0
    )
    
    # 임시 설정
    cfg = AppConfig()
    cfg.broker.output_dir = str(tmp_path / "orders")
    
    # Monkeypatch results_path via property override is tricky, let's just make it run
    # and verify index.html is valid. Actually we can wrap it or modify the test cfg
    # since we use cfg.results_path, we can't easily override dynamic properties unless we patch PROJECT_ROOT.
    
    # We will just patch PROJECT_ROOT temporarily
    import trader.config as config_module
    old_root = config_module.PROJECT_ROOT
    config_module.PROJECT_ROOT = tmp_path
    
    try:
        generate_report(trades, equity_curve, metrics, "2025-01-01", "2025-01-04", cfg)
        
        # Verify files generated
        reports_dir = tmp_path / "reports" / "backtest" / "latest"
        assert reports_dir.exists(), "latest 폴더가 생성되어야 함"
        assert (reports_dir / "index.html").exists(), "index.html 이 생성되어야 함"
        assert (reports_dir / "equity_curve.png").exists(), "에쿼티 차트가 생성되어야 함"
        assert (reports_dir / "drawdown.png").exists(), "Drawdown 차트가 생성되어야 함"
        assert (reports_dir / "trades.csv").exists(), "trades.csv 가 생성되어야 함"
        assert (reports_dir / "metrics.json").exists(), "metrics.json 이 생성되어야 함"
        
        # Verify backward compatibility copy
        results_dir = tmp_path / "results"
        assert results_dir.exists()
        assert (results_dir / "equity_curve.png").exists()
        assert (results_dir / "trades.csv").exists()
        assert (results_dir / "metrics.txt").exists()
    finally:
        config_module.PROJECT_ROOT = old_root
