# Moon Dev Strategies Knowledge Base

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

- Indexed videos: **234** (processed into summaries so far)
- Transcript coverage: **233/234** available, **1** missing
- Status: incremental pipeline enabled; rerun `build_summaries.py` to continue from checkpoint.

## Confidence Policy

- `high`: transcript+metadata with clear tactical detail
- `medium`: transcript exists but heuristic extraction
- `low`: transcript unavailable or fetch failure; title/description-only inference

No transcript content is fabricated. Missing transcript is explicitly marked per video.
