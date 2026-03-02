"""broker_base.py — BrokerBase 추상 클래스"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class BrokerBase(ABC):
    """브로커 추상 인터페이스.

    모든 브로커 구현체는 이 클래스를 상속한다.
    """

    @abstractmethod
    def place_order(
        self,
        ticker: str,
        side: str,
        qty: int,
        order_type: str = "MARKET",
        price: float = 0.0,
    ) -> str:
        """주문 전송. 반환값: order_id"""
        ...

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """주문 취소. 성공 시 True."""
        ...

    @abstractmethod
    def get_positions(self) -> Dict[str, dict]:
        """현재 보유 포지션 반환.

        Returns:
            {'ticker': {'qty': int, 'avg_price': float}}
        """
        ...
