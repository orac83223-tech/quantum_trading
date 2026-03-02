"""html_report.py — Jinja2 템플릿을 활용한 정적 HTML 리포트 생성"""

import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import pandas as pd
from datetime import date, datetime

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    Environment = None
    FileSystemLoader = None


def _get_jinja_env() -> "Environment":
    if Environment is None:
        raise ImportError("jinja2 가 설치되어 있지 않습니다. 리포트 생성이 불가능합니다.")
    
    templates_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(templates_dir)))
    
    # 템플릿용 커스텀 필터 등록
    def format_krw(value):
        if value is None:
            return "0"
        try:
            return f"{float(value):,.0f}"
        except (ValueError, TypeError):
            return str(value)

    def format_pct(value):
        if value is None:
            return "0.00"
        try:
            return f"{float(value):.2f}"
        except (ValueError, TypeError):
            return str(value)
            
    env.filters['krw'] = format_krw
    env.filters['pct'] = format_pct
    return env


def render_backtest_report(
    run_dir: Path,
    config_dict: Dict[str, Any],
    metrics_dict: Dict[str, Any],
    equity_df: pd.DataFrame,
    trades_df: pd.DataFrame
) -> Path:
    """백테스트 결과를 HTML 문서로 렌더링하고 run_dir/index.html 로 저장한다."""
    env = _get_jinja_env()
    template = env.get_template("backtest.html")
    
    # 월별 수익 테이블 계산 (단순화: 월말 자산 기준)
    # equity_df는 index가 없고 'date', 'equity' 컬럼이 있어야 함
    # 혹은 List[Tuple]에서 넘어왔다면 외부에서 맞춰서 넘기거나 여기서 조정
    monthly_returns = []
    if not equity_df.empty and 'date' in equity_df.columns:
        df = equity_df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # Resample to monthly end
        monthly = df['equity'].resample('ME').last()
        
        # 이전 값이 NaN일 수 있으므로 pct_change 후 dropna
        ret = monthly.pct_change() * 100
        
        # 월별 트레이드 수 추출
        if not trades_df.empty and 'exit_date' in trades_df.columns:
            tr_df = trades_df.copy()
            tr_df['exit_date'] = pd.to_datetime(tr_df['exit_date'])
            tr_df.set_index('exit_date', inplace=True)
            monthly_trades = tr_df.resample('ME').size()
        else:
            monthly_trades = pd.Series(0, index=monthly.index)
            
        for d, row in ret.dropna().items():
            trade_count = monthly_trades.get(d) or 0
            if pd.isna(trade_count):
                trade_count = 0
                
            monthly_returns.append({
                "month": d.strftime("%Y-%m"),
                "return_pct": row,
                "trades": int(trade_count)
            })
            
        # 최신 월이 먼저 오도록 정렬
        monthly_returns.sort(key=lambda x: x["month"], reverse=True)

    # 최근 200개 트레이드만 HTML 에 포함
    recent_trades = []
    if not trades_df.empty:
        # PnL 관련 파싱 처리 (없을 수도 있음 대비)
        t_df = trades_df.tail(200).copy()
        # 역순 정렬: 최근 것이 위로
        t_df = t_df.iloc[::-1]
        recent_trades = t_df.to_dict('records')

    context = {
        "run_id": run_dir.name,
        "config": config_dict,
        "metrics": metrics_dict,
        "monthly_returns": monthly_returns,
        "trades": recent_trades,
        "total_trades_count": len(trades_df) if not trades_df.empty else 0,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    output_html = template.render(**context)
    
    out_path = run_dir / "index.html"
    out_path.write_text(output_html, encoding="utf-8")
    return out_path


def render_portfolio_report(
    out_dir: Path,
    asof_date: str,
    portfolio_summary: List[Dict[str, Any]],
    cash: float,
    orders_df: Optional[pd.DataFrame] = None,
    config_dict: Optional[Dict[str, Any]] = None
) -> Path:
    """포트폴리오 상태를 HTML 로 렌더링하고 out_dir/index.html 에 저장한다."""
    env = _get_jinja_env()
    template = env.get_template("portfolio.html")
    
    # 평가액 총합 계산
    total_market_value = 0.0
    total_pnl = 0.0
    
    for pos in portfolio_summary:
        mkt_val = pos.get('mkt_value', 0.0)
        pnl = pos.get('unrealized_pnl', 0.0)
        total_market_value += mkt_val
        total_pnl += pnl

    total_equity = cash + total_market_value
    
    # 주문 스냅샷
    orders_list = []
    if orders_df is not None and not orders_df.empty:
        orders_list = orders_df.to_dict('records')
        
    context = {
        "asof_date": asof_date,
        "cash": cash,
        "total_market_value": total_market_value,
        "total_pnl": total_pnl,
        "total_equity": total_equity,
        "positions_count": len(portfolio_summary),
        "positions": portfolio_summary,
        "orders": orders_list,
        "config": config_dict or {},
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    output_html = template.render(**context)
    
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "index.html"
    out_path.write_text(output_html, encoding="utf-8")
    return out_path

