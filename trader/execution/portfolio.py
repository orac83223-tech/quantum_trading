"""portfolio.py — 오픈 포지션 상태 관리"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Dict, List, Optional, Any
from pathlib import Path

from trader.config import AppConfig, get_config
from trader.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class Position:
    """단일 포지션 상태."""
    ticker: str
    entry_date: object
    entry_price: float
    qty: int
    sl: float
    tp1: float
    bars_held: int = 0
    tp1_hit: bool = False
    remaining_ratio: float = 1.0
    unrealized_pnl: float = 0.0


class Portfolio:
    """포트폴리오 = 오픈 포지션 집합 관리."""

    def __init__(self, cfg: Optional[AppConfig] = None, asof: Optional[str] = None, cash: float = 0.0):
        if cfg is None:
            cfg = get_config()
        self.max_positions = cfg.risk.max_positions
        self.positions: Dict[str, Position] = {}
        self.asof = asof or str(date.today())
        self.cash = cash

    def can_add(self) -> bool:
        """포지션 추가가 가능한지 확인."""
        return len(self.positions) < self.max_positions

    def has_position(self, ticker: str) -> bool:
        """이미 해당 종목 포지션이 있는지 확인."""
        return ticker in self.positions

    def add_position(self, pos: Position) -> None:
        """포지션 추가."""
        if not self.can_add():
            log.warning("최대 포지션 수 초과: %d/%d", len(self.positions), self.max_positions)
            return
        if self.has_position(pos.ticker):
            log.warning("이미 보유 중: %s", pos.ticker)
            return
        self.positions[pos.ticker] = pos
        log.info("포지션 추가: %s (진입가: %.0f, SL: %.0f, TP1: %.0f)",
                 pos.ticker, pos.entry_price, pos.sl, pos.tp1)

    def remove_position(self, ticker: str) -> Optional[Position]:
        """포지션 제거."""
        pos = self.positions.pop(ticker, None)
        if pos:
            log.info("포지션 제거: %s", ticker)
        return pos

    def update_price(self, ticker: str, current_price: float) -> None:
        """현재가 기준 미실현 손익 갱신."""
        if ticker in self.positions:
            pos = self.positions[ticker]
            pos.unrealized_pnl = (current_price - pos.entry_price) * pos.qty

    def get_summary(self) -> List[dict]:
        """포트폴리오 요약."""
        return [
            {
                "ticker": pos.ticker,
                "entry_price": pos.entry_price,
                "qty": pos.qty,
                "sl": pos.sl,
                "tp1": pos.tp1,
                "bars_held": pos.bars_held,
                "unrealized_pnl": pos.unrealized_pnl,
            }
            for pos in self.positions.values()
        ]

    @property
    def count(self) -> int:
        return len(self.positions)

    def to_dict(self) -> Dict[str, Any]:
        """JSON 저장을 위한 딕셔너리 변환."""
        pos_dict = {}
        for k, v in self.positions.items():
            # datetime.date 객체가 있을 수 있으므로 문자열 변환
            d = asdict(v)
            d['entry_date'] = str(d['entry_date'])
            pos_dict[k] = d
            
        return {
            "asof": self.asof,
            "cash": self.cash,
            "positions": pos_dict
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any], cfg: Optional[AppConfig] = None) -> "Portfolio":
        """딕셔너리에서 포트폴리오 복원."""
        pf = cls(cfg=cfg, asof=data.get("asof"), cash=data.get("cash", 0.0))
        for tk, p_data in data.get("positions", {}).items():
            pos = Position(**p_data)
            pf.positions[tk] = pos
        return pf

    def save_json(self, filepath: Path) -> None:
        """상태를 JSON 파일로 저장."""
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=4, ensure_ascii=False)
        log.info("포트폴리오 저장: %s", filepath)

    @classmethod
    def load_json(cls, filepath: Path, cfg: Optional[AppConfig] = None) -> Optional["Portfolio"]:
        """JSON 파일에서 포트폴리오 로드."""
        if not filepath.exists():
            log.warning("포트폴리오 파일 없음: %s", filepath)
            return None
            
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        log.info("포트폴리오 로드: %s (asof=%s)", filepath, data.get('asof'))
        return cls.from_dict(data, cfg=cfg)
