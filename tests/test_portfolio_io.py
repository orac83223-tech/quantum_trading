"""test_portfolio_io.py — 포트폴리오 Save/Load 검증"""

from trader.execution.portfolio import Portfolio, Position
from trader.config import AppConfig

def test_portfolio_json_roundtrip(tmp_path):
    cfg = AppConfig()
    pf = Portfolio(cfg, asof="2026-03-03", cash=15000000.0)
    
    pos1 = Position(
        ticker="005930",
        entry_date="2026-03-01",
        entry_price=70000,
        qty=100,
        sl=65000,
        tp1=80000
    )
    pos2 = Position(
        ticker="035420",
        entry_date="2026-03-02",
        entry_price=180000,
        qty=50,
        sl=170000,
        tp1=200000,
        unrealized_pnl=500000.0
    )
    
    pf.add_position(pos1)
    pf.add_position(pos2)
    
    filepath = tmp_path / "portfolio.json"
    pf.save_json(filepath)
    
    assert filepath.exists()
    
    pf_loaded = Portfolio.load_json(filepath, cfg)
    
    assert pf_loaded is not None
    assert pf_loaded.asof == "2026-03-03"
    assert pf_loaded.cash == 15000000.0
    assert pf_loaded.count == 2
    
    loaded_pos2 = pf_loaded.positions["035420"]
    assert loaded_pos2.entry_price == 180000
    assert loaded_pos2.qty == 50
    assert loaded_pos2.unrealized_pnl == 500000.0
