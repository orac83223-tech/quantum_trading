"""report.py — equity curve + trades.csv 출력"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

from trader.backtest.metrics import BacktestMetrics, format_metrics
from trader.config import AppConfig, get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


def save_trades_csv(
    trades: list,
    output_path: Optional[Path] = None,
    cfg: Optional[AppConfig] = None,
) -> Path:
    """트레이드 목록을 CSV 로 저장한다."""
    if cfg is None:
        cfg = get_config()
    if output_path is None:
        output_path = cfg.results_path / "trades.csv"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for t in trades:
        rows.append({
            "ticker": t.ticker,
            "entry_date": str(t.entry_date),
            "entry_price": t.entry_price,
            "exit_date": str(t.exit_date),
            "exit_price": t.exit_price,
            "sl": t.sl,
            "tp1": t.tp1,
            "Ls": t.Ls,
            "Lr": t.Lr,
            "size": t.size,
            "pnl": t.pnl,
            "pnl_r": t.pnl_r,
            "exit_reason": t.exit_reason,
            "score": t.score,
            "reasons": ",".join(t.reasons),
        })

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info("트레이드 저장: %s (%d trades)", output_path, len(trades))
    return output_path


def save_equity_curve(
    equity_curve: List[Tuple[object, float]],
    output_path: Optional[Path] = None,
    cfg: Optional[AppConfig] = None,
) -> Optional[Path]:
    """에쿼티 커브를 PNG 이미지로 저장한다."""
    if cfg is None:
        cfg = get_config()
    if output_path is None:
        output_path = cfg.results_path / "equity_curve.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not equity_curve:
        log.warning("에쿼티 커브 데이터 없음")
        return None

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.ticker as mticker

        dates = [e[0] for e in equity_curve]
        equities = [e[1] for e in equity_curve]

        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(dates, equities, linewidth=1.2, color="#2196F3")
        ax.fill_between(dates, equities, alpha=0.1, color="#2196F3")

        ax.set_title("Quantum–Gann Confluence v1 — Equity Curve", fontsize=14, fontweight="bold")
        ax.set_xlabel("Date")
        ax.set_ylabel("Equity (KRW)")
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        fig.savefig(output_path, dpi=150)
        plt.close(fig)

        log.info("에쿼티 커브 저장: %s", output_path)
        return output_path

    except ImportError:
        log.warning("matplotlib 미설치: 에쿼티 커브 이미지 생성 불가")
        return None


def save_metrics(
    metrics: BacktestMetrics,
    start: str = "",
    end: str = "",
    output_path: Optional[Path] = None,
    cfg: Optional[AppConfig] = None,
) -> Path:
    """메트릭스를 텍스트 파일로 저장한다."""
    if cfg is None:
        cfg = get_config()
    if output_path is None:
        output_path = cfg.results_path / "metrics.txt"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    text = format_metrics(metrics, start, end)
    output_path.write_text(text, encoding="utf-8")
    log.info("메트릭스 저장: %s", output_path)
    return output_path


import json
import shutil
from datetime import datetime

def save_metrics_json(
    metrics: BacktestMetrics,
    output_path: Path,
) -> Path:
    """메트릭스를 JSON 파일로 저장한다."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # dataclass 를 dict 로 변환
    import dataclasses
    data = dataclasses.asdict(metrics)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    log.info("메트릭스 JSON 저장: %s", output_path)
    return output_path


def generate_report(
    trades: list,
    equity_curve: List[Tuple[object, float]],
    metrics: BacktestMetrics,
    start: str = "",
    end: str = "",
    cfg: Optional[AppConfig] = None,
    no_report: bool = False,
) -> None:
    """전체 백테스트 리포트를 생성한다."""
    if cfg is None:
        cfg = get_config()

    if no_report:
        log.info("리포트 생성 건너뜀 (--no-report)")
        return

    # 1. Run ID 생성 (YYYYMMDD_HHMMSS)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 2. 결과 저장 디렉토리 설정
    project_root = cfg.results_path.parent
    reports_dir = project_root / "reports" / "backtest"
    run_dir = reports_dir / run_id
    latest_dir = reports_dir / "latest"
    
    run_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. 데이터 저장
    trades_path = save_trades_csv(trades, output_path=run_dir / "trades.csv", cfg=cfg)
    metrics_txt_path = save_metrics(metrics, start, end, output_path=run_dir / "metrics.txt", cfg=cfg)
    metrics_json_path = save_metrics_json(metrics, output_path=run_dir / "metrics.json")
    
    # DataFrame 변환
    import pandas as pd
    trades_df = pd.DataFrame([t.__dict__ for t in trades]) if trades else pd.DataFrame()
    equity_df = pd.DataFrame(equity_curve, columns=['date', 'equity']) if equity_curve else pd.DataFrame(columns=['date', 'equity'])
    
    # Equity CSV 저장
    equity_csv_path = run_dir / "equity.csv"
    equity_df.to_csv(equity_csv_path, index=False)
    
    # 4. 차트 생성
    from trader.reporting.plots import make_equity_curve_png, make_drawdown_png
    eq_png_path = make_equity_curve_png(equity_curve, run_dir / "equity_curve.png")
    dd_png_path = make_drawdown_png(equity_curve, run_dir / "drawdown.png")
    
    # 5. HTML 리포트 생성
    from trader.reporting.html_report import render_backtest_report
    # config dict 변환 방어 로직
    import dataclasses
    try:
        config_dict = dataclasses.asdict(cfg)
    except Exception:
        config_dict = {}
        
    metrics_dict = dataclasses.asdict(metrics)
    
    html_path = render_backtest_report(
        run_dir=run_dir,
        config_dict=config_dict,
        metrics_dict=metrics_dict,
        equity_df=equity_df,
        trades_df=trades_df
    )
    
    # 6. latest 덮어쓰기 복사
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(run_dir, latest_dir)
    
    # 7. 기존 results/ 경로 호환 유지
    cfg.results_path.mkdir(parents=True, exist_ok=True)
    if trades_path.exists():
        shutil.copy2(trades_path, cfg.results_path / "trades.csv")
    if metrics_txt_path.exists():
        shutil.copy2(metrics_txt_path, cfg.results_path / "metrics.txt")
    if eq_png_path and eq_png_path.exists():
        shutil.copy2(eq_png_path, cfg.results_path / "equity_curve.png")

    # 콘솔 출력
    text = format_metrics(metrics, start, end)
    print("\n" + text)
    print(f"\n결과 저장: (Run ID: {run_id})")
    print(f"  ✓ {html_path.relative_to(project_root)}")
    print(f"  ✓ {latest_dir.relative_to(project_root)}/index.html")
    print(f"  ✓ 호환: results/equity_curve.png, results/trades.csv, results/metrics.txt")
