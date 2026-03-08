#!/usr/bin/env python3
import csv
import json
import subprocess
from pathlib import Path

CHANNEL_URL = "https://www.youtube.com/channel/UCN7D80fY9xMYu5mHhUhXEFw/videos"
OUT_DIR = Path("data/raw/index")
OUT_DIR.mkdir(parents=True, exist_ok=True)

raw_path = OUT_DIR / "channel_videos_raw.json"
jsonl_path = Path("data/processed/video_index.jsonl")
csv_path = Path("data/processed/video_index.csv")
json_path = Path("data/processed/video_index.json")

cmd = [
    "yt-dlp", "--no-update", "--flat-playlist", "--dump-single-json", CHANNEL_URL
]
res = subprocess.run(cmd, capture_output=True, text=True, check=True)
raw_path.write_text(res.stdout)
obj = json.loads(res.stdout)
entries = obj.get("entries", [])

rows = []
for i, e in enumerate(entries, start=1):
    vid = e.get("id")
    url = f"https://www.youtube.com/watch?v={vid}" if vid else None
    rows.append({
        "position": i,
        "video_id": vid,
        "title": e.get("title"),
        "upload_date": e.get("upload_date"),
        "url": url,
        "channel_id": obj.get("id"),
        "channel_title": obj.get("channel") or obj.get("title"),
        "availability": e.get("availability"),
        "duration": e.get("duration"),
        "view_count": e.get("view_count"),
    })

jsonl_path.parent.mkdir(parents=True, exist_ok=True)
with jsonl_path.open("w") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")

with csv_path.open("w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)

json_path.write_text(json.dumps({
    "channel_id": obj.get("id"),
    "channel_title": obj.get("title"),
    "total_videos": len(rows),
    "generated_from": CHANNEL_URL,
    "videos": rows,
}, ensure_ascii=False, indent=2))

print(f"Indexed {len(rows)} videos")
