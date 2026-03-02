"""logging.py — 로깅 설정"""

from __future__ import annotations

import logging
import sys

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """루트 로거 설정."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format=_LOG_FORMAT,
        datefmt=_DATE_FORMAT,
        stream=sys.stderr,
    )


def get_logger(name: str) -> logging.Logger:
    """이름 기반 로거를 반환한다."""
    return logging.getLogger(name)
