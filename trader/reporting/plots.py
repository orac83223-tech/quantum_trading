"""plots.py — Matplotlib 을 활용한 차트 생성 (오프라인 HTML 리포트용)"""

from typing import List, Tuple, Optional
from pathlib import Path

import pandas as pd
import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker
    import matplotlib.dates as mdates
except ImportError:
    plt = None


def _check_matplotlib():
    """Matplotlib 임포트 확인"""
    if plt is None:
        raise ImportError("matplotlib 이 설치되어 있지 않습니다.")


def make_equity_curve_png(
    equity_curve: List[Tuple[object, float]],
    out_path: Path,
    title: str = "Equity Curve"
) -> Path:
    """에쿼티 커브를 PNG 이미지로 저장한다."""
    _check_matplotlib()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not equity_curve:
        # 빈 이미지 생성
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No Data", ha='center', va='center')
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path

    # Extract dates and equity values
    dates = [e[0] for e in equity_curve]
    equities = [e[1] for e in equity_curve]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dates, equities, linewidth=1.5, color="#2563eb") # Tailwind Blue-600
    ax.fill_between(dates, equities, alpha=0.15, color="#2563eb")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Equity (KRW)", fontsize=11, labelpad=10)
    
    # y축 포맷팅
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    
    # 날짜 포맷팅 및 눈금
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    ax.grid(True, linestyle='--', alpha=0.5, color='#e5e7eb') # Tailwind Gray-200
    
    # 테두리 정리
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#9ca3af')
    ax.spines['bottom'].set_color('#9ca3af')
    ax.tick_params(colors='#4b5563', which='both')

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches='tight', transparent=False, facecolor='white')
    plt.close(fig)

    return out_path


def make_drawdown_png(
    equity_curve: List[Tuple[object, float]],
    out_path: Path,
    title: str = "Drawdown %"
) -> Path:
    """Drawdown을 차트로 그려 PNG 이미지로 저장한다."""
    _check_matplotlib()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not equity_curve:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.text(0.5, 0.5, "No Data", ha='center', va='center')
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        return out_path

    dates = [e[0] for e in equity_curve]
    equities = [e[1] for e in equity_curve]
    
    df = pd.DataFrame({'date': dates, 'equity': equities})
    
    # DD 계산: (equity / equity.cummax - 1) * 100
    df['peak'] = df['equity'].cummax()
    df['dd_pct'] = (df['equity'] / df['peak'] - 1) * 100

    fig, ax = plt.subplots(figsize=(12, 4))
    
    # 빨간색으로 음수 영역을 채운다
    ax.plot(df['date'], df['dd_pct'], linewidth=1.0, color="#ef4444") # Tailwind Red-500
    ax.fill_between(df['date'], df['dd_pct'], 0, alpha=0.3, color="#ef4444")

    ax.set_title(title, fontsize=14, fontweight="bold", pad=15)
    ax.set_ylabel("Drawdown (%)", fontsize=11, labelpad=10)
    
    # y축 포맷팅
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x:.1f}%"))
    
    # y축은 0 이 최대값 (Drawdown 은 항상 음수)
    ax.set_ylim(bottom=df['dd_pct'].min() * 1.05 if not df.empty else -10, top=0)

    # 날짜 포맷팅 및 눈금
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.xticks(rotation=45)
    
    ax.grid(True, linestyle='--', alpha=0.5, color='#e5e7eb')
    
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#9ca3af')
    ax.spines['bottom'].set_color('#9ca3af')
    ax.tick_params(colors='#4b5563', which='both')

    plt.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches='tight', transparent=False, facecolor='white')
    plt.close(fig)

    return out_path

