"""YAML設定の読込。全パラメータは config/*.yaml に一元化する。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DataConfig:
    data_dir: str = "data"
    interval: str = "1h"
    history_days: int = 730


@dataclass
class UniverseConfig:
    top_n: int = 30
    volume_lookback_days: int = 30
    min_listing_days: int = 90


@dataclass
class SignalConfig:
    name: str = "momentum"
    lookback_hours: int = 168


@dataclass
class PortfolioConfig:
    quantile: float = 0.2


@dataclass
class RebalanceConfig:
    frequency_hours: int = 24


@dataclass
class CostsConfig:
    fee_bps: float = 5.0
    slippage_bps: float = 5.0


@dataclass
class BacktestConfig:
    initial_capital: float = 10000.0
    holdout_fraction: float = 0.25
    use_holdout: bool = False
    benchmark_symbol: str = "BTCUSDT"


@dataclass
class Config:
    data: DataConfig = field(default_factory=DataConfig)
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    signal: SignalConfig = field(default_factory=SignalConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    rebalance: RebalanceConfig = field(default_factory=RebalanceConfig)
    costs: CostsConfig = field(default_factory=CostsConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)


_SECTIONS = {
    "data": DataConfig,
    "universe": UniverseConfig,
    "signal": SignalConfig,
    "portfolio": PortfolioConfig,
    "rebalance": RebalanceConfig,
    "costs": CostsConfig,
    "backtest": BacktestConfig,
}


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    kwargs = {}
    for section, cls in _SECTIONS.items():
        values = raw.get(section) or {}
        unknown = set(values) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise ValueError(f"config [{section}] に未知のキー: {sorted(unknown)}")
        kwargs[section] = cls(**values)
    return Config(**kwargs)
