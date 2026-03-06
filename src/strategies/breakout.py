"""Trend-regime breakout strategy on hourly bars."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class BreakoutParams:
    tp_pct: float = 0.03
    sl_pct: float = 0.18
    leverage: float = 3.0
    resistance_lookback_days: int = 20


class BreakoutStrategy:
    """Breakout strategy using prior daily resistance.

    Why shift(1): The current day's high is unknowable in real time. Using shift avoids look-ahead bias.
    """

    def __init__(self, params: Optional[BreakoutParams] = None) -> None:
        self.params = params or BreakoutParams()

    def generate_signals(self, hourly: pd.DataFrame, regime_col: str = "regime") -> pd.DataFrame:
        """Generate entry and exits for trend regimes."""
        df = hourly.copy().sort_index()
        if regime_col not in df.columns:
            df[regime_col] = "trend_up"

        daily_high = df["high"].resample("1D").max()
        resistance = daily_high.rolling(self.params.resistance_lookback_days, min_periods=5).max().shift(1)

        df["resistance"] = resistance.reindex(df.index, method="ffill")
        df["entry_long"] = (df["close"] > df["resistance"]) & df[regime_col].str.startswith("trend")

        df["tp_price"] = df["close"] * (1 + self.params.tp_pct)
        df["sl_price"] = df["close"] * (1 - self.params.sl_pct)
        df["leverage"] = self.params.leverage

        return df
