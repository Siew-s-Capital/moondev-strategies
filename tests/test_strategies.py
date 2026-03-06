from __future__ import annotations

import numpy as np
import pandas as pd
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.backtest import Backtester
from src.regime_detector import RegimeDetector
from src.risk_manager import RiskManager
from src.strategies.breakout import BreakoutStrategy
from src.strategies.liquidation_reversal import LiquidationReversalStrategy


def sample_ohlcv(rows: int = 300) -> pd.DataFrame:
    idx = pd.date_range("2025-01-01", periods=rows, freq="h", tz="UTC")
    close = 100 + np.cumsum(np.random.normal(0, 0.5, size=rows))
    return pd.DataFrame(
        {
            "open": close,
            "high": close + np.random.uniform(0.1, 1.0, size=rows),
            "low": close - np.random.uniform(0.1, 1.0, size=rows),
            "close": close,
            "volume": np.random.uniform(1_000, 2_000, size=rows),
        },
        index=idx,
    )


def test_regime_detector_outputs_labels() -> None:
    df = sample_ohlcv(400)
    out = RegimeDetector(n_components=7).fit_predict(df)
    assert "regime" in out.frame.columns
    assert out.frame["regime"].notna().all()


def test_breakout_has_shifted_resistance() -> None:
    df = sample_ohlcv(400)
    signals = BreakoutStrategy().generate_signals(df)
    first_valid = signals["resistance"].first_valid_index()
    assert first_valid is not None


def test_liquidation_reversal_generates_flags() -> None:
    df = sample_ohlcv(100)
    df["hlp_zscore"] = np.linspace(-3, 3, len(df))
    df["liquidation_pressure"] = 2.0
    df["smart_money_confirm"] = True
    out = LiquidationReversalStrategy().generate_signals(df)
    assert out["long_signal"].any()
    assert out["short_signal"].any()


def test_risk_manager_size_non_negative() -> None:
    rm = RiskManager()
    size = rm.compute_position_size(
        equity=10_000,
        entry_price=100,
        stop_price=98,
        win_rate=0.55,
        reward_risk=1.5,
    )
    assert size >= 0


def test_backtester_metrics_present() -> None:
    df = sample_ohlcv(200)
    df["position"] = np.where(np.arange(len(df)) % 10 < 5, 1.0, 0.0)
    _, metrics = Backtester().run(df, signal_col="position")
    assert {"sharpe", "sortino", "max_drawdown", "exposure"}.issubset(metrics.keys())
