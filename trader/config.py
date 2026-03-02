"""config.py — config.yaml 로드 + 파라미터 데이터클래스"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml
from dotenv import load_dotenv


# ── 기본 경로 ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"


# ── 데이터클래스 ───────────────────────────────────────────
@dataclass
class UniverseConfig:
    market: str = "KOSDAQ"
    min_listed_days: int = 250
    min_value_krw: int = 5_000_000_000
    min_price: int = 1000
    exclude_list: List[str] = field(default_factory=list)


@dataclass
class IndicatorsConfig:
    atr_period: int = 14
    band_atr_mult: float = 0.25
    pivot_bars: int = 3
    so9_angles: List[int] = field(default_factory=lambda: [45, 90, 135, 180, 270, 360])
    so9_k_cycles: List[int] = field(default_factory=lambda: [0, 1])
    time_bars: List[int] = field(default_factory=lambda: [45, 90, 135, 180, 270, 360])
    time_window: int = 5
    gann_scale_n: int = 90
    gann_penalty_fraction: float = 0.5


@dataclass
class StrategyConfig:
    score_threshold: int = 2
    confirmation: str = "sma5"          # sma5 | prev_high
    trend_filter: str = "sma200"        # sma200 | sma50 | none
    use_qpl_confluence: bool = False
    use_breakout_retest: bool = False
    sl_atr_mult: float = 1.0
    tp1_ratio: float = 0.5
    time_stop_bars: int = 45


@dataclass
class EvGateConfig:
    enabled: bool = True
    lookback_bars: int = 700
    success_bars: int = 45
    cost_buffer_pct: float = 0.005


@dataclass
class RiskConfig:
    risk_pct_per_trade: float = 0.005
    max_positions: int = 10
    daily_stop_R: int = 2
    cost_roundtrip: float = 0.005
    slippage: float = 0.001


@dataclass
class BrokerConfig:
    default: str = "csv"
    output_dir: str = "orders/"


@dataclass
class DataConfig:
    cache_dir: str = "data/cache"
    source: str = "pykrx"


@dataclass
class AppConfig:
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    indicators: IndicatorsConfig = field(default_factory=IndicatorsConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    ev_gate: EvGateConfig = field(default_factory=EvGateConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    broker: BrokerConfig = field(default_factory=BrokerConfig)
    data: DataConfig = field(default_factory=DataConfig)

    @property
    def cache_path(self) -> Path:
        return PROJECT_ROOT / self.data.cache_dir

    @property
    def output_path(self) -> Path:
        return PROJECT_ROOT / self.broker.output_dir

    @property
    def results_path(self) -> Path:
        return PROJECT_ROOT / "results"


# ── 로더 ──────────────────────────────────────────────────
def _dict_to_dataclass(dc_cls, d: dict):
    """dict → 데이터클래스 (불필요 키 무시)"""
    import dataclasses
    field_names = {f.name for f in dataclasses.fields(dc_cls)}
    filtered = {k: v for k, v in d.items() if k in field_names}
    return dc_cls(**filtered)


def load_config(path: Optional[Path] = None) -> AppConfig:
    """config.yaml 을 읽어 AppConfig 를 반환한다."""
    load_dotenv(ENV_PATH)
    path = path or CONFIG_PATH

    if not path.exists():
        return AppConfig()

    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    return AppConfig(
        universe=_dict_to_dataclass(UniverseConfig, raw.get("universe", {})),
        indicators=_dict_to_dataclass(IndicatorsConfig, raw.get("indicators", {})),
        strategy=_dict_to_dataclass(StrategyConfig, raw.get("strategy", {})),
        ev_gate=_dict_to_dataclass(EvGateConfig, raw.get("ev_gate", {})),
        risk=_dict_to_dataclass(RiskConfig, raw.get("risk", {})),
        broker=_dict_to_dataclass(BrokerConfig, raw.get("broker", {})),
        data=_dict_to_dataclass(DataConfig, raw.get("data", {})),
    )


# ── 싱글턴 ────────────────────────────────────────────────
_cfg: Optional[AppConfig] = None


def get_config() -> AppConfig:
    global _cfg
    if _cfg is None:
        _cfg = load_config()
    return _cfg
