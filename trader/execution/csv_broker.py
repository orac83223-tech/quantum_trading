"""csv_broker.py — CsvBroker (주문 파일만 생성, 실거래 없음)"""

from __future__ import annotations

import csv
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from trader.config import get_config
from trader.execution.broker_base import BrokerBase
from trader.utils.logging import get_logger

log = get_logger(__name__)


class CsvBroker(BrokerBase):
    """주문을 CSV 파일로만 저장하는 드라이런 브로커.

    실거래는 일절 수행하지 않는다.
    """

    def __init__(self, output_dir: str | Path | None = None):
        cfg = get_config()
        self.output_dir = Path(output_dir) if output_dir else cfg.output_path
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.orders: List[dict] = []
        self.positions: Dict[str, dict] = {}

    def place_order(
        self,
        ticker: str,
        side: str,
        qty: int,
        order_type: str = "MARKET",
        price: float = 0.0,
    ) -> str:
        order_id = str(uuid.uuid4())[:8]
        order = {
            "order_id": order_id,
            "timestamp": datetime.now().isoformat(),
            "ticker": ticker,
            "side": side,
            "qty": qty,
            "order_type": order_type,
            "price": price,
            "status": "FILLED_SIM",
        }
        self.orders.append(order)

        # 포지션 시뮬레이션
        if side.upper() == "BUY":
            if ticker in self.positions:
                pos = self.positions[ticker]
                total_qty = pos["qty"] + qty
                pos["avg_price"] = (pos["avg_price"] * pos["qty"] + price * qty) / total_qty
                pos["qty"] = total_qty
            else:
                self.positions[ticker] = {"qty": qty, "avg_price": price}
        elif side.upper() == "SELL":
            if ticker in self.positions:
                self.positions[ticker]["qty"] -= qty
                if self.positions[ticker]["qty"] <= 0:
                    del self.positions[ticker]

        log.info("CSV 주문: %s %s %s x%d @ %.0f", order_id, side, ticker, qty, price)
        return order_id

    def cancel_order(self, order_id: str) -> bool:
        for order in self.orders:
            if order["order_id"] == order_id:
                order["status"] = "CANCELLED"
                log.info("CSV 주문 취소: %s", order_id)
                return True
        return False

    def get_positions(self) -> Dict[str, dict]:
        return dict(self.positions)

    def save_orders(self, filename: str = "orders_next_open.csv") -> Path:
        """누적된 주문을 CSV 파일로 저장한다."""
        path = self.output_dir / filename
        if not self.orders:
            log.warning("저장할 주문이 없습니다")
            return path

        fieldnames = list(self.orders[0].keys())
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.orders)

        log.info("주문 저장: %s (%d 건)", path, len(self.orders))
        return path
