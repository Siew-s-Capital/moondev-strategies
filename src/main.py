"""Main orchestrator for regime-aware strategy pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict

import pandas as pd
import yaml

from backtest import Backtester, BacktestConfig
from regime_detector import RegimeDetector, load_hourly_csv
from risk_manager import RiskConfig, RiskManager
from strategies.breakout import BreakoutStrategy, BreakoutParams
from strategies.liquidation_reversal import LiquidationReversalStrategy, LiquidationReversalParams


def load_config(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_positions(df: pd.DataFrame) -> pd.Series:
    """Translate strategy boolean signals to a simple net position."""
    pos = pd.Series(0.0, index=df.index)
    pos[df.get("entry_long", False)] = 1.0
    pos[df.get("short_signal", False)] = -1.0
    pos[df.get("long_signal", False)] = 1.0
    return pos.ffill().fillna(0.0)


def run_pipeline(config_path: Path) -> Dict[str, float]:
    config = load_config(config_path)
    ohlcv = load_hourly_csv(config["data"]["hourly_csv"])

    regime = RegimeDetector(**config["regime_detector"]).fit_predict(ohlcv)
    frame = regime.frame

    breakout = BreakoutStrategy(BreakoutParams(**config["breakout_strategy"]))
    frame = breakout.generate_signals(frame)

    liq = LiquidationReversalStrategy(LiquidationReversalParams(**config["liquidation_reversal"]))
    for col, default in {
        "hlp_zscore": 0.0,
        "liquidation_pressure": 0.0,
        "smart_money_confirm": False,
    }.items():
        if col not in frame.columns:
            frame[col] = default
    frame = liq.generate_signals(frame)

    frame["position"] = build_positions(frame)

    _risk = RiskManager(RiskConfig(**config["risk_management"]))
    # RiskManager is integrated as a pre-trade guardrail in live mode.
    # For this baseline backtest we keep vectorized positions for reproducibility.

    bt = Backtester(BacktestConfig(**config["backtest"]))
    _, metrics = bt.run(frame, signal_col="position")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description="MoonDev strategy orchestrator")
    parser.add_argument("--config", type=Path, default=Path("config/strategy_config.yaml"))
    args = parser.parse_args()

    metrics = run_pipeline(args.config)
    print("Backtest complete")
    for k, v in metrics.items():
        print(f"{k}: {v:.4f}")


if __name__ == "__main__":
    main()
