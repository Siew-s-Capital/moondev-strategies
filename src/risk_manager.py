"""Portfolio-level risk controls and position sizing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np
import pandas as pd


@dataclass
class RiskConfig:
    max_risk_per_trade: float = 0.02
    daily_kill_switch: float = -0.03
    fractional_kelly: float = 0.5
    correlation_cap: float = 0.8


class RiskManager:
    """Apply hard risk limits before order placement."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.daily_pnl: Dict[pd.Timestamp, float] = {}

    def compute_position_size(
        self,
        equity: float,
        entry_price: float,
        stop_price: float,
        win_rate: float,
        reward_risk: float,
    ) -> float:
        """Size position by min(risk-cap sizing, fractional Kelly sizing)."""
        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit <= 0:
            return 0.0

        risk_budget_units = (equity * self.config.max_risk_per_trade) / risk_per_unit
        kelly_f = self.kelly_fraction(win_rate, reward_risk) * self.config.fractional_kelly
        kelly_units = max(0.0, (equity * kelly_f) / entry_price)
        return float(max(0.0, min(risk_budget_units, kelly_units)))

    @staticmethod
    def kelly_fraction(win_rate: float, reward_risk: float) -> float:
        """Classic Kelly formula: f* = p - (1-p)/b."""
        if reward_risk <= 0:
            return 0.0
        return max(0.0, win_rate - ((1 - win_rate) / reward_risk))

    def update_daily_pnl(self, ts: pd.Timestamp, pnl: float) -> None:
        day = ts.normalize()
        self.daily_pnl[day] = self.daily_pnl.get(day, 0.0) + pnl

    def kill_switch_triggered(self, ts: pd.Timestamp, equity: float) -> bool:
        day = ts.normalize()
        pnl = self.daily_pnl.get(day, 0.0)
        return pnl / equity <= self.config.daily_kill_switch

    def passes_correlation_cap(self, candidate_returns: pd.Series, active_returns: pd.DataFrame) -> bool:
        """Reject new position if correlation to active book is too high."""
        if active_returns.empty:
            return True
        corrs = active_returns.corrwith(candidate_returns).dropna().abs()
        if corrs.empty:
            return True
        return bool(corrs.max() <= self.config.correlation_cap)
