"""Liquidation-driven mean reversion strategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

import pandas as pd


@dataclass
class LiquidationReversalParams:
    z_threshold: float = 2.0
    liquidation_pressure_threshold: float = 1.5
    hard_stop_bps: float = 35.0
    time_stop_minutes: int = 12


class LiquidationReversalStrategy:
    """Fade liquidation extremes when momentum participants are trapped."""

    def __init__(self, params: Optional[LiquidationReversalParams] = None) -> None:
        self.params = params or LiquidationReversalParams()

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate long/short setup flags and risk exits."""
        required = {"close", "hlp_zscore", "liquidation_pressure", "smart_money_confirm"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing columns for liquidation reversal: {sorted(missing)}")

        out = df.copy().sort_index()
        p = self.params

        out["long_signal"] = (
            (out["hlp_zscore"] < -p.z_threshold)
            & (out["liquidation_pressure"] > p.liquidation_pressure_threshold)
            & (out["smart_money_confirm"].astype(bool))
        )
        out["short_signal"] = (
            (out["hlp_zscore"] > p.z_threshold)
            & (out["liquidation_pressure"] > p.liquidation_pressure_threshold)
        )

        out["hard_stop_pct"] = p.hard_stop_bps / 10_000
        out["time_stop_at"] = out.index + timedelta(minutes=p.time_stop_minutes)
        return out
