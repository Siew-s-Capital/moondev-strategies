"""Simple walk-forward backtest with fees/slippage and core metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import pandas as pd


@dataclass
class BacktestConfig:
    fee_bps: float = 4.0
    slippage_bps: float = 3.0
    annualization: int = 24 * 365


class Backtester:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(self, frame: pd.DataFrame, signal_col: str = "position") -> Tuple[pd.DataFrame, Dict[str, float]]:
        """Run vectorized backtest from pre-computed position series."""
        df = frame.copy().sort_index()
        df["ret"] = df["close"].pct_change().fillna(0.0)
        df[signal_col] = df[signal_col].fillna(0.0)
        df["turnover"] = df[signal_col].diff().abs().fillna(0.0)

        trading_cost = (self.config.fee_bps + self.config.slippage_bps) / 10_000
        df["strategy_ret"] = (df[signal_col].shift(1).fillna(0.0) * df["ret"]) - (df["turnover"] * trading_cost)
        df["equity_curve"] = (1 + df["strategy_ret"]).cumprod()

        metrics = self.compute_metrics(df["strategy_ret"], df["equity_curve"], df[signal_col])
        return df, metrics

    def walk_forward_splits(self, n_rows: int, train_size: int, test_size: int):
        """Yield train/test index windows for walk-forward validation."""
        start = 0
        while start + train_size + test_size <= n_rows:
            train_end = start + train_size
            test_end = train_end + test_size
            yield (start, train_end), (train_end, test_end)
            start += test_size

    def compute_metrics(self, strategy_ret: pd.Series, equity_curve: pd.Series, position: pd.Series) -> Dict[str, float]:
        """Compute risk-adjusted performance and exposure metrics."""
        r = strategy_ret.dropna()
        if r.empty:
            return {"sharpe": 0.0, "sortino": 0.0, "max_drawdown": 0.0, "exposure": 0.0}

        ann = self.config.annualization
        sharpe = (r.mean() / (r.std() + 1e-12)) * np.sqrt(ann)
        downside = r[r < 0]
        sortino = (r.mean() / (downside.std() + 1e-12)) * np.sqrt(ann)

        running_max = equity_curve.cummax()
        drawdown = equity_curve / running_max - 1
        max_dd = drawdown.min()

        exposure = (position.abs() > 0).mean()
        return {
            "sharpe": float(sharpe),
            "sortino": float(sortino),
            "max_drawdown": float(max_dd),
            "exposure": float(exposure),
        }
