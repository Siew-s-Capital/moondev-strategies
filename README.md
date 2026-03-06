# MoonDev Strategies

Regime-aware crypto strategy stack inspired by MoonDev research videos.

## Included Components

- **HMM Regime Detector** (`src/regime_detector.py`)
  - Features: returns, volatility, volume_change, Bollinger Band width
  - Model: `GaussianHMM(n_components=7)`
  - Labels states into `trend_up`, `trend_down`, `range`, `shock`

- **Breakout Strategy** (`src/strategies/breakout.py`)
  - Entry: 1H close > prior daily 20D rolling resistance
  - Uses `.shift(1)` to avoid look-ahead bias
  - TP: +3%, SL: -18%, leverage: 3x

- **Liquidation Reversal** (`src/strategies/liquidation_reversal.py`)
  - Long: z-score < -2 + high liquidation pressure + smart money confirmation
  - Short: z-score > 2 + high liquidation pressure
  - Hard stop: 35 bps, time stop: 12 minutes

- **Risk Manager** (`src/risk_manager.py`)
  - Position risk cap: 2% per trade
  - Daily kill-switch: stop at -3%
  - Fractional Kelly sizing
  - Correlation cap checks

- **Backtest Framework** (`src/backtest.py`)
  - Walk-forward split utility
  - Fee + slippage cost model
  - Metrics: Sharpe, Sortino, max drawdown, exposure

- **Main Orchestrator** (`src/main.py`)
  - Config-driven YAML pipeline
  - Regime detect -> strategy signals -> backtest
  - Supports backtest/paper/live mode config flags (backtest implemented in this baseline)

## Project Structure

```
moondev-strategies/
├── src/
├── config/
├── data/
├── tests/
├── requirements.txt
└── README.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run

```bash
python src/main.py --config config/strategy_config.yaml
```

## Test

```bash
pytest -q
```

## Notes

- `data/` is gitignored except for `.gitkeep`; sample CSV is provided for local runs.
- No API keys are embedded. Plug live feeds through adapters before deploying.
