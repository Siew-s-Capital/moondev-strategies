"""Hidden Markov Model based market regime detector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM


@dataclass
class RegimeDetectionResult:
    """Container for fitted HMM outputs."""

    frame: pd.DataFrame
    model: GaussianHMM
    state_to_label: Dict[int, str]


class RegimeDetector:
    """Detect latent market regimes from hourly OHLCV features.

    We use HMM because regimes are persistent and transitions are stateful.
    A memoryless classifier often flickers in sideways markets.
    """

    def __init__(self, n_components: int = 7, random_state: int = 42, n_iter: int = 250) -> None:
        self.n_components = n_components
        self.random_state = random_state
        self.n_iter = n_iter

    @staticmethod
    def build_features(ohlcv: pd.DataFrame) -> pd.DataFrame:
        """Build regime features from hourly OHLCV."""
        required = {"open", "high", "low", "close", "volume"}
        missing = required - set(ohlcv.columns)
        if missing:
            raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")

        df = ohlcv.copy()
        df["returns"] = np.log(df["close"]).diff()
        df["volatility"] = df["returns"].rolling(24, min_periods=24).std()
        df["volume_change"] = df["volume"].pct_change()

        rolling_mean = df["close"].rolling(20, min_periods=20).mean()
        rolling_std = df["close"].rolling(20, min_periods=20).std()
        bb_upper = rolling_mean + (2 * rolling_std)
        bb_lower = rolling_mean - (2 * rolling_std)
        df["bb_width"] = (bb_upper - bb_lower) / rolling_mean

        return df.dropna().copy()

    def fit_predict(self, ohlcv: pd.DataFrame) -> RegimeDetectionResult:
        """Fit Gaussian HMM and return labeled regimes."""
        features_df = self.build_features(ohlcv)
        x = features_df[["returns", "volatility", "volume_change", "bb_width"]].values

        model = GaussianHMM(
            n_components=self.n_components,
            covariance_type="full",
            n_iter=self.n_iter,
            random_state=self.random_state,
        )
        model.fit(x)
        states = model.predict(x)

        features_df["state"] = states
        mapping = self._map_states_to_labels(features_df)
        features_df["regime"] = features_df["state"].map(mapping)
        return RegimeDetectionResult(frame=features_df, model=model, state_to_label=mapping)

    @staticmethod
    def _map_states_to_labels(features_df: pd.DataFrame) -> Dict[int, str]:
        """Map latent states to human-readable tags using state statistics."""
        grouped = features_df.groupby("state")[["returns", "volatility"]].mean()
        ret_q1, ret_q3 = grouped["returns"].quantile([0.25, 0.75])
        vol_q3 = grouped["volatility"].quantile(0.75)

        labels: Dict[int, str] = {}
        for state, row in grouped.iterrows():
            if row["volatility"] >= vol_q3:
                labels[state] = "shock"
            elif row["returns"] >= ret_q3:
                labels[state] = "trend_up"
            elif row["returns"] <= ret_q1:
                labels[state] = "trend_down"
            else:
                labels[state] = "range"
        return labels


def load_hourly_csv(path: str) -> pd.DataFrame:
    """Load hourly OHLCV CSV with datetime index."""
    df = pd.read_csv(path)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df = df.set_index("timestamp")
    return df.sort_index()
