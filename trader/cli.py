"""cli.py — typer CLI 진입점

명령어:
  backtest  — 백테스트 실행
  signals   — 신호 생성 (장 마감 후 실행)
  paper     — 페이퍼 트레이딩
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from trader.config import get_config, load_config
from trader.utils.logging import setup_logging, get_logger

app = typer.Typer(
    name="trader",
    help="Quantum–Gann Confluence Trader v1",
    add_completion=False,
)

report_app = typer.Typer(help="리포트 생성 관련 명령어")
portfolio_app = typer.Typer(help="포트폴리오 관리 관련 명령어")

app.add_typer(report_app, name="report")
app.add_typer(portfolio_app, name="portfolio")

console = Console()
log = get_logger(__name__)


@app.command()
def backtest(
    start: str = typer.Option("2015-01-01", help="백테스트 시작일 (YYYY-MM-DD)"),
    end: str = typer.Option("2026-01-01", help="백테스트 종료일 (YYYY-MM-DD)"),
    universe: str = typer.Option("kosdaq", help="유니버스 (kosdaq | kospi | all)"),
    ticker: Optional[str] = typer.Option(None, help="단일 종목 테스트 (선택)"),
    no_report: bool = typer.Option(False, "--no-report", help="리포트 생성 생략"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
):
    """전략 백테스트를 실행한다."""
    setup_logging(log_level)
    cfg = get_config()

    start_date = datetime.strptime(start, "%Y-%m-%d").date()
    end_date = datetime.strptime(end, "%Y-%m-%d").date()

    console.print(f"\n[bold blue]🚀 Quantum–Gann Confluence v1 백테스트[/bold blue]")
    console.print(f"   기간: {start} ~ {end}")
    console.print(f"   유니버스: {universe.upper()}\n")

    from trader.data.cache import load_or_fetch
    from trader.data.pykrx_loader import get_market_tickers, filter_universe
    from trader.backtest.engine import run_backtest
    from trader.backtest.metrics import compute_metrics
    from trader.backtest.report import generate_report

    # 종목 목록
    if ticker:
        tickers = [ticker]
        console.print(f"   단일 종목: {ticker}")
    else:
        console.print("   종목 목록 로딩 중...")
        if universe.lower() == "all":
            tickers = get_market_tickers("KOSDAQ", end_date) + get_market_tickers("KOSPI", end_date)
            # 중복 제거
            tickers = list(dict.fromkeys(tickers))
        else:
            tickers = get_market_tickers(universe, end_date)

    # 데이터 로드
    console.print(f"   데이터 수집 중... ({len(tickers)} 종목)")
    ticker_data = {}
    for i, tk in enumerate(tickers):
        try:
            df = load_or_fetch(tk, start_date, end_date)
            if not df.empty and len(df) >= cfg.universe.min_listed_days:
                ticker_data[tk] = df
        except Exception as e:
            log.debug("데이터 수집 실패 %s: %s", tk, e)

        if (i + 1) % 100 == 0:
            console.print(f"   ... {i+1}/{len(tickers)} 완료")

    # 유니버스 필터
    if not ticker:
        filtered = filter_universe(list(ticker_data.keys()), ticker_data, cfg)
        ticker_data = {tk: ticker_data[tk] for tk in filtered}

    console.print(f"   유효 종목: {len(ticker_data)}")

    # 백테스트 실행
    console.print("\n   [bold]백테스트 실행 중...[/bold]")
    trades, equity_curve = run_backtest(ticker_data, cfg)

    # 메트릭스
    years = (end_date - start_date).days / 365.25
    metrics = compute_metrics(trades, equity_curve, years=years)

    # 리포트
    generate_report(trades, equity_curve, metrics, start, end, cfg, no_report=no_report)

    console.print("\n[bold green]✓ 백테스트 완료![/bold green]")


@report_app.command("backtest")
def report_backtest(
    run_id: str = typer.Option(..., help="백테스트 실행 ID"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
):
    """지정된 백테스트 실행(run_id)의 리포트를 다시 생성한다."""
    setup_logging(log_level)
    cfg = get_config()
    
    project_root = cfg.results_path.parent
    run_dir = project_root / "reports" / "backtest" / run_id
    
    if not run_dir.exists():
        console.print(f"[bold red]❌ Run ID '{run_id}' 를 찾을 수 없습니다.[/bold red]")
        raise typer.Exit(1)
        
    import json
    import pandas as pd
    from trader.reporting.html_report import render_backtest_report
    import dataclasses
    
    metrics_path = run_dir / "metrics.json"
    equity_path = run_dir / "equity.csv"
    trades_path = run_dir / "trades.csv"
    
    if not (metrics_path.exists() and equity_path.exists()):
        console.print(f"[bold red]❌ 필수 데이터 파일(metrics.json, equity.csv)이 부족합니다.[/bold red]")
        raise typer.Exit(1)
        
    with open(metrics_path, "r", encoding="utf-8") as f:
        metrics_dict = json.load(f)
        
    equity_df = pd.read_csv(equity_path)
    trades_df = pd.read_csv(trades_path) if trades_path.exists() else pd.DataFrame()
    
    try:
        config_dict = dataclasses.asdict(cfg)
    except Exception:
        config_dict = {}
        
    html_path = render_backtest_report(
        run_dir=run_dir,
        config_dict=config_dict,
        metrics_dict=metrics_dict,
        equity_df=equity_df,
        trades_df=trades_df
    )
    
    console.print(f"\n[bold green]✓ 리포트 재생성 완료: {html_path}[/bold green]")


@report_app.command("portfolio")
def report_portfolio(
    date_str: str = typer.Option(..., "--date", help="기준일 (YYYY-MM-DD)"),
    portfolio_path: Optional[str] = typer.Option(None, "--portfolio", help="portfolio.json 파일 경로 (선택)"),
    orders_path: Optional[str] = typer.Option(None, "--orders", help="주문 내역 파일 경로 (선택)"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
):
    """현재 포트폴리오를 기반으로 리포트를 생성한다."""
    setup_logging(log_level)
    cfg = get_config()
    target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    
    # 주말/휴일 보정
    from trader.calendar_krx import get_trading_days
    # 최근 10일치 거래일 긁어서 target_date 보다 작거나 같은 가장 가까운 거래일 탐색
    past_days = get_trading_days(date(target_date.year - 1, 1, 1), target_date)
    if not past_days:
        asof_date = target_date
    else:
        asof_date = past_days[-1]
        
    if asof_date != target_date:
        console.print(f"[yellow]⚠️ {target_date}는 휴일입니다. 최종 거래일 {asof_date} 기준으로 보정합니다.[/yellow]")

    portfolio_file = Path(portfolio_path) if portfolio_path else cfg.results_path.parent / "state" / "portfolio.json"
    orders_file = Path(orders_path) if orders_path else cfg.output_path / "orders_next_open.csv"
    
    from trader.execution.portfolio import Portfolio
    import pandas as pd
    from trader.data.cache import load_or_fetch
    
    pf = Portfolio.load_json(portfolio_file, cfg)
    if not pf:
        console.print("[yellow]포트폴리오 상태 파일이 없어 빈 상태로 시작합니다.[/yellow]")
        pf = Portfolio(cfg, asof=str(asof_date))
        
    orders_df = pd.DataFrame()
    if orders_file.exists():
        orders_df = pd.read_csv(orders_file)
        
    # 현재가 가져오기 및 summary 갱신
    summary = pf.get_summary()
    from datetime import timedelta
    for item in summary:
        tk = item["ticker"]
        try:
            # 늦어도 최근 10일치 가져와서 가장 마지막 종목 가격 
            df = load_or_fetch(tk, asof_date - timedelta(days=15), asof_date)
            if not df.empty:
                last_close = df["Close"].iloc[-1]
                item["mkt_value"] = last_close * item["qty"]
                item["unrealized_pnl"] = (last_close - item["entry_price"]) * item["qty"]
            else:
                item["mkt_value"] = item["entry_price"] * item["qty"]
        except Exception:
            item["mkt_value"] = item["entry_price"] * item["qty"]

    from trader.reporting.html_report import render_portfolio_report
    import dataclasses
    
    project_root = cfg.results_path.parent
    report_out_dir = project_root / "reports" / "portfolio" / str(asof_date)
    latest_dir = project_root / "reports" / "portfolio" / "latest"
    
    try:
        config_dict = dataclasses.asdict(cfg)
    except Exception:
        config_dict = {}

    html_path = render_portfolio_report(
        out_dir=report_out_dir,
        asof_date=str(asof_date),
        portfolio_summary=summary,
        cash=pf.cash,
        orders_df=orders_df,
        config_dict=config_dict,
    )
    
    import shutil
    if latest_dir.exists():
        shutil.rmtree(latest_dir)
    shutil.copytree(report_out_dir, latest_dir)

    console.print(f"\n[bold green]✓ 포트폴리오 리포트 생성 완료: {html_path}[/bold green]")
    console.print(f"  ✓ {latest_dir.relative_to(project_root)}/index.html")


@portfolio_app.command("import")
def portfolio_import(
    csv_path: str = typer.Option(..., "--csv", help="포트폴리오 CSV 경로 (ticker,qty,avg_price)"),
    date_str: str = typer.Option(..., "--asof", help="기준일 (YYYY-MM-DD)"),
    cash: float = typer.Option(0.0, "--cash", help="보유 현금"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
):
    """CSV 파일로부터 포지션을 읽어 portfolio.json 으로 저장한다."""
    setup_logging(log_level)
    cfg = get_config()
    
    file_path = Path(csv_path)
    if not file_path.exists():
        console.print(f"[bold red]❌ 파일이 존재하지 않습니다: {csv_path}[/bold red]")
        raise typer.Exit(1)
        
    import pandas as pd
    from trader.execution.portfolio import Portfolio, Position
    
    try:
        df = pd.read_csv(file_path)
    except Exception as e:
        console.print(f"[bold red]❌ CSV 읽기 실패: {e}[/bold red]")
        raise typer.Exit(1)
        
    pf = Portfolio(cfg, asof=date_str, cash=cash)
    
    count = 0
    for idx, row in df.iterrows():
        try:
            tk = str(row['ticker']).zfill(6)
            qty = int(row['qty'])
            avg_price = float(row['avg_price'])
            
            # 없는 정보(SL/TP 등)는 더미값으로 채움.
            pos = Position(
                ticker=tk,
                entry_date=date_str,
                entry_price=avg_price,
                qty=qty,
                sl=avg_price * 0.9, # 임의 -10%
                tp1=avg_price * 1.5 # 임의 +50%
            )
            pf.add_position(pos)
            count += 1
        except Exception as e:
            console.print(f"[yellow]⚠️ 행 파싱 에러 ({idx}): {row} - {e}[/yellow]")
            
    out_path = cfg.results_path.parent / "state" / "portfolio.json"
    pf.save_json(out_path)
    console.print(f"\n[bold green]✓ 포트폴리오 {count} 종목 저장 완료: {out_path}[/bold green]")


@app.command()
def signals(
    date_str: str = typer.Option(
        ..., "--date", help="신호 생성 기준일 (YYYY-MM-DD)"
    ),
    universe: str = typer.Option("kosdaq", help="유니버스 (kosdaq | kospi | all)"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
    live: bool = typer.Option(False, "--live", help="실거래 모드 (⚠️ 위험)"),
):
    """장 마감 후 신호를 생성하고 주문 파일을 출력한다."""
    setup_logging(log_level)
    cfg = get_config()

    if live:
        console.print("[bold red]⚠️  --live 모드는 아직 구현되지 않았습니다.[/bold red]")
        raise typer.Exit(1)

    signal_date = datetime.strptime(date_str, "%Y-%m-%d").date()

    console.print(f"\n[bold blue]📡 신호 생성[/bold blue] (기준일: {date_str})")

    from trader.data.cache import load_or_fetch
    from trader.data.pykrx_loader import get_market_tickers, filter_universe
    from trader.strategy.qg_confluence_v1 import compute_signals
    from trader.strategy.ev_gate import compute_ev_gate
    from trader.execution.csv_broker import CsvBroker
    from trader.execution.risk import calculate_position_size

    # 데이터 로드 (최근 2년)
    from datetime import timedelta
    lookback_start = signal_date - timedelta(days=800)

    if universe.lower() == "all":
        tickers = get_market_tickers("KOSDAQ", signal_date) + get_market_tickers("KOSPI", signal_date)
        tickers = list(dict.fromkeys(tickers))
    else:
        tickers = get_market_tickers(universe, signal_date)
        
    console.print(f"   종목 수: {len(tickers)}")

    broker = CsvBroker()
    equity = 100_000_000  # 기본 자본금 (설정 파일에서 읽도록 확장 가능)

    all_signals = []

    for tk in tickers:
        try:
            df = load_or_fetch(tk, lookback_start, signal_date)
            if df.empty or len(df) < 250:
                continue

            sigs = compute_signals(tk, df, cfg)
            # 기준일 기준 최신 신호만 필터
            for sig in sigs:
                if hasattr(sig.signal_date, 'date'):
                    sig_d = sig.signal_date.date()
                else:
                    sig_d = sig.signal_date
                if sig_d == signal_date:
                    # EV Gate
                    if cfg.ev_gate.enabled:
                        ev = compute_ev_gate(sig.entry_price_est, sig.sl, sig.tp1)
                        if not ev.passed:
                            continue

                    # 포지션 사이징
                    ps = calculate_position_size(
                        equity, sig.entry_price_est, sig.sl, sig.gann_penalty, cfg
                    )
                    if ps.shares <= 0:
                        continue

                    all_signals.append({
                        "ticker": tk,
                        "side": "BUY",
                        "qty": ps.shares,
                        "entry_price_est": sig.entry_price_est,
                        "sl": sig.sl,
                        "tp1": sig.tp1,
                        "score": sig.score,
                        "reason": "+".join(sig.reasons),
                    })

                    broker.place_order(
                        tk, "BUY", ps.shares,
                        price=sig.entry_price_est,
                    )
        except Exception as e:
            log.debug("신호 생성 실패 %s: %s", tk, e)

    # 결과 출력
    if all_signals:
        table = Table(title=f"📋 신호 목록 ({date_str})")
        table.add_column("Ticker", style="cyan")
        table.add_column("Side", style="green")
        table.add_column("Qty", justify="right")
        table.add_column("Entry Est.", justify="right")
        table.add_column("SL", justify="right")
        table.add_column("TP1", justify="right")
        table.add_column("Score", justify="center")
        table.add_column("Reason")

        for sig in all_signals:
            table.add_row(
                sig["ticker"],
                sig["side"],
                str(sig["qty"]),
                f"{sig['entry_price_est']:,.0f}",
                f"{sig['sl']:,.0f}",
                f"{sig['tp1']:,.0f}",
                str(sig["score"]),
                sig["reason"],
            )

        console.print(table)
        path = broker.save_orders()
        console.print(f"\n[bold green]✓ 주문 파일 저장: {path}[/bold green]")
    else:
        console.print("\n[yellow]신호 없음[/yellow]")


@app.command()
def paper(
    from_date: str = typer.Option(..., "--from", help="시작일 (YYYY-MM-DD)"),
    to_date: str = typer.Option(..., "--to", help="종료일 (YYYY-MM-DD)"),
    universe: str = typer.Option("kosdaq", help="유니버스 (kosdaq | kospi | all)"),
    broker_type: str = typer.Option("mock", "--broker", help="브로커 타입 (mock | csv)"),
    log_level: str = typer.Option("INFO", help="로그 레벨"),
):
    """페이퍼 트레이딩 시뮬레이션을 실행한다."""
    setup_logging(log_level)
    cfg = get_config()

    start_date = datetime.strptime(from_date, "%Y-%m-%d").date()
    end_date = datetime.strptime(to_date, "%Y-%m-%d").date()

    console.print(f"\n[bold blue]📝 페이퍼 트레이딩[/bold blue]")
    console.print(f"   기간: {from_date} ~ {to_date}")
    console.print(f"   브로커: {broker_type}")

    from trader.backtest.engine import run_backtest
    from trader.backtest.metrics import compute_metrics, format_metrics
    from trader.data.cache import load_or_fetch
    from trader.data.pykrx_loader import get_market_tickers, filter_universe

    # 데이터 로드
    if universe.lower() == "all":
        tickers = get_market_tickers("KOSDAQ", end_date) + get_market_tickers("KOSPI", end_date)
        tickers = list(dict.fromkeys(tickers))
    else:
        tickers = get_market_tickers(universe, end_date)
        
    console.print(f"   종목 수: {len(tickers)}")

    from datetime import timedelta
    data_start = start_date - timedelta(days=400)

    ticker_data = {}
    for tk in tickers[:50]:  # 페이퍼: 상위 50 종목으로 제한
        try:
            df = load_or_fetch(tk, data_start, end_date)
            if not df.empty and len(df) >= 250:
                ticker_data[tk] = df
        except Exception:
            pass

    filtered = filter_universe(list(ticker_data.keys()), ticker_data, cfg)
    ticker_data = {tk: ticker_data[tk] for tk in filtered}

    console.print(f"   유효 종목: {len(ticker_data)}")
    console.print("\n   [bold]시뮬레이션 실행 중...[/bold]")

    trades, equity_curve = run_backtest(ticker_data, cfg)
    years = (end_date - start_date).days / 365.25
    metrics = compute_metrics(trades, equity_curve, years=max(years, 0.1))

    text = format_metrics(metrics, from_date, to_date)
    console.print(f"\n{text}")
    console.print(f"\n[bold green]✓ 페이퍼 트레이딩 완료! ({len(trades)} trades)[/bold green]")


if __name__ == "__main__":
    app()
