"""mock_broker.py — MockBroker (페이퍼 시뮬레이션)"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Dict, List, Optional

import pandas as pd

from trader.execution.broker_base import BrokerBase
from trader.utils.logging import get_logger

log = get_logger(__name__)


class MockBroker(BrokerBase):
    """다음날 시가를 체결가로 가정하는 시뮬레이션 브로커.

    페이퍼 트레이딩 용도.
    """

    def __init__(self):
        self.orders: List[dict] = []
        self.positions: Dict[str, dict] = {}
        self.order_queue: List[dict] = []  # 다음날 시가 체결 대기

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
            "ticker": ticker,
            "side": side,
            "qty": qty,
            "order_type": order_type,
            "limit_price": price,
            "status": "PENDING",
            "fill_price": 0.0,
        }
        self.order_queue.append(order)
        self.orders.append(order)
        log.info("Mock 주문 접수: %s %s %s x%d", order_id, side, ticker, qty)
        return order_id

    def process_fills(self, ohlcv_today: Dict[str, pd.Series]) -> List[dict]:
        """오늘 시가로 대기 중인 주문을 체결 처리한다.

        Args:
            ohlcv_today: {ticker: 오늘 OHLCV Series (Open, High, Low, Close, Volume)}

        Returns:
            체결된 주문 리스트
        """
        filled = []
        remaining = []

        for order in self.order_queue:
            ticker = order["ticker"]
            if ticker not in ohlcv_today:
                remaining.append(order)
                continue

            open_price = ohlcv_today[ticker]["Open"]
            order["fill_price"] = open_price
            order["status"] = "FILLED"

            # 포지션 업데이트
            side = order["side"].upper()
            qty = order["qty"]

            if side == "BUY":
                if ticker in self.positions:
                    pos = self.positions[ticker]
                    total_qty = pos["qty"] + qty
                    pos["avg_price"] = (
                        pos["avg_price"] * pos["qty"] + open_price * qty
                    ) / total_qty
                    pos["qty"] = total_qty
                else:
                    self.positions[ticker] = {"qty": qty, "avg_price": open_price}
            elif side == "SELL":
                if ticker in self.positions:
                    self.positions[ticker]["qty"] -= qty
                    if self.positions[ticker]["qty"] <= 0:
                        del self.positions[ticker]

            filled.append(order)
            log.info(
                "Mock 체결: %s %s %s x%d @ %.0f",
                order["order_id"], side, ticker, qty, open_price,
            )

        self.order_queue = remaining
        return filled

    def cancel_order(self, order_id: str) -> bool:
        for order in self.order_queue:
            if order["order_id"] == order_id:
                order["status"] = "CANCELLED"
                self.order_queue.remove(order)
                log.info("Mock 주문 취소: %s", order_id)
                return True
        return False

    def get_positions(self) -> Dict[str, dict]:
        return dict(self.positions)
