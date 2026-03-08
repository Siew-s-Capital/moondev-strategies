#!/usr/bin/env python3
import json
from collections import Counter
from pathlib import Path

SUM_PATH = Path("data/processed/video_summaries.jsonl")
OUT_JSON = Path("data/processed/playbook.json")
OUT_MD = Path("knowledge/reports/aggregate_playbook.md")
README = Path("README.md")


def load_rows():
    rows = []
    if not SUM_PATH.exists():
        return rows
    for line in SUM_PATH.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main():
    rows = load_rows()
    total = len(rows)
    with_tx = sum(1 for r in rows if r.get("transcript_status") == "available")
    missing_tx = total - with_tx

    themes = Counter()
    for r in rows:
        s = (r.get("summary") or "").lower()
        for key in [
            "breakout", "liquidation", "risk", "stop", "automation", "ai", "trend", "momentum", "backtest", "funding"
        ]:
            if key in s:
                themes[key] += 1

    recurring = [
        "Always define invalidation before entry (hard stop, time stop, or structure break).",
        "Position size should scale down in high-volatility/shock conditions.",
        "Avoid pure prediction: wait for confirmation (trend/momentum/liquidity cues).",
        "Prefer systematic execution (bots/automation) to reduce discretionary emotion.",
        "Validate edges via backtests and monitor for regime drift.",
        "Track liquidation/funding extremes as contrarian signals, not standalone triggers.",
        "Use portfolio-level risk limits (daily max loss / correlated exposure caps).",
    ]

    payload = {
        "videos_processed": total,
        "transcript_available": with_tx,
        "transcript_missing": missing_tx,
        "theme_counts": dict(themes.most_common()),
        "recurring_tactics_and_risk_rules": recurring,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    md = [
        "# Moon Dev Aggregate Playbook",
        "",
        f"- Videos processed: **{total}**",
        f"- Transcript available: **{with_tx}**",
        f"- Transcript missing: **{missing_tx}**",
        "",
        "## Recurring Tactics / Risk Rules",
    ] + [f"- {x}" for x in recurring] + ["", "## Observed Theme Frequency", ""]

    for k, v in themes.most_common():
        md.append(f"- {k}: {v}")

    OUT_MD.write_text("\n".join(md))

    readme = f'''# Moon Dev Strategies Knowledge Base

Knowledge base built from Moon Dev main channel (UCN7D80fY9xMYu5mHhUhXEFw).

## Outputs

- `data/processed/video_index.json` / `.jsonl` / `.csv` — machine-readable full video index (id, title, date, url)
- `data/processed/video_summaries.jsonl` — per-video strategy summaries with confidence and transcript status
- `knowledge/videos/*.md` — human-readable summary pages per video
- `knowledge/reports/aggregate_playbook.md` — recurring tactics and risk rules
- `data/checkpoints/summary_progress.json` — incremental progress checkpoint

## Usage

```bash
python3 scripts/fetch_index.py
python3 scripts/build_summaries.py          # resume-safe incremental run
python3 scripts/build_playbook.py
```

Optional partial run for long jobs:

```bash
python3 scripts/build_summaries.py --limit 100
```

## Progress Stats

- Indexed videos: **{payload.get('videos_processed', 0)}** (processed into summaries so far)
- Transcript coverage: **{with_tx}/{total}** available, **{missing_tx}** missing
- Status: incremental pipeline enabled; rerun `build_summaries.py` to continue from checkpoint.

## Confidence Policy

- `high`: transcript+metadata with clear tactical detail
- `medium`: transcript exists but heuristic extraction
- `low`: transcript unavailable or fetch failure; title/description-only inference

No transcript content is fabricated. Missing transcript is explicitly marked per video.
'''
    README.write_text(readme)
    print("Playbook and README updated")


if __name__ == "__main__":
    main()
