#!/usr/bin/env python3
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen, Request

INDEX_PATH = Path("data/processed/video_index.json")
META_DIR = Path("data/raw/video_meta")
TRANS_DIR = Path("data/raw/transcripts")
OUT_JSONL = Path("data/processed/video_summaries.jsonl")
CHECKPOINT = Path("data/checkpoints/summary_progress.json")
KNOW_DIR = Path("knowledge/videos")

META_DIR.mkdir(parents=True, exist_ok=True)
TRANS_DIR.mkdir(parents=True, exist_ok=True)
OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
KNOW_DIR.mkdir(parents=True, exist_ok=True)


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t or "").strip()


def parse_vtt_text(raw: str) -> str:
    out = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("WEBVTT") or "-->" in s or s.isdigit() or s.startswith("NOTE"):
            continue
        s = re.sub(r"<[^>]+>", "", s)
        out.append(s)
    return clean_text(" ".join(out))


def parse_json3_text(raw: str) -> str:
    try:
        obj = json.loads(raw)
    except Exception:
        return ""
    chunks = []
    for ev in obj.get("events", []):
        for seg in ev.get("segs", []) or []:
            txt = seg.get("utf8")
            if txt:
                chunks.append(txt)
    return clean_text(" ".join(chunks))


def fetch_caption_from_meta(video_id: str, meta: dict):
    caps = meta.get("subtitles") or {}
    auto = meta.get("automatic_captions") or {}

    for source_name, source in [("subtitles", caps), ("automatic_captions", auto)]:
        for lang in ["en", "en-US", "en-GB", "en-orig"]:
            tracks = source.get(lang) or []
            for tr in tracks:
                url = tr.get("url")
                ext = (tr.get("ext") or "").lower()
                if not url:
                    continue
                try:
                    req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
                    raw = urlopen(req, timeout=20).read().decode("utf-8", errors="ignore")
                    if not raw:
                        continue
                    text = ""
                    if ext in {"vtt", "ttml", "srv1", "srv2", "srv3"}:
                        text = parse_vtt_text(raw)
                    elif ext == "json3":
                        text = parse_json3_text(raw)
                    else:
                        text = parse_vtt_text(raw)
                    if text:
                        out_file = TRANS_DIR / f"{video_id}.{source_name}.{lang}.{ext or 'txt'}"
                        out_file.write_text(raw)
                        return text, out_file.name
                except Exception:
                    continue
    return "", None


def heuristic_summary(title: str, description: str, transcript: str) -> tuple[str, str, str]:
    corpus = " ".join([title or "", description or "", transcript[:5000] or ""]).lower()
    motifs = []
    if any(k in corpus for k in ["breakout", "break out", "resistance", "support"]):
        motifs.append("Breakout/breakdown around support-resistance levels")
    if any(k in corpus for k in ["liquidation", "squeeze", "funding"]):
        motifs.append("Liquidation and funding-driven mean reversion setups")
    if any(k in corpus for k in ["risk", "stop", "drawdown", "position size", "loss"]):
        motifs.append("Explicit risk controls (stops, sizing, drawdown awareness)")
    if any(k in corpus for k in ["ai", "bot", "agent", "gpt", "automate"]):
        motifs.append("Automation/AI tooling for strategy execution")
    if any(k in corpus for k in ["trend", "momentum", "ema", "moving average"]):
        motifs.append("Trend or momentum confirmation before entries")
    if any(k in corpus for k in ["backtest", "win rate", "sharpe", "expectancy"]):
        motifs.append("Backtesting/performance validation emphasis")

    if transcript:
        status = "available"
        confidence = "medium"
    else:
        status = "missing"
        confidence = "low"

    summary = "; ".join(motifs[:3]) if motifs else "Topic inferred from title/description; no clear tactical signals detected"
    return summary, status, confidence


def append_result(obj):
    with OUT_JSONL.open("a") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def write_checkpoint(processed, total):
    CHECKPOINT.write_text(json.dumps({
        "processed": processed,
        "total": total,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }, indent=2))


def fetch_meta(video_id: str, url: str):
    meta_path = META_DIR / f"{video_id}.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())
    cmd = ["yt-dlp", "--no-update", "--skip-download", "--dump-json", url]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-500:])
    meta = json.loads(res.stdout.splitlines()[-1])
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2))
    return meta


def load_done_ids():
    done = set()
    if OUT_JSONL.exists():
        for line in OUT_JSONL.read_text().splitlines():
            if line.strip():
                try:
                    done.add(json.loads(line)["video_id"])
                except Exception:
                    pass
    return done


def main(limit: int | None = None, force_rebuild: bool = False):
    idx = json.loads(INDEX_PATH.read_text())
    videos = idx["videos"]

    if force_rebuild:
        OUT_JSONL.write_text("")
        done = set()
    else:
        done = load_done_ids()

    processed_count = len(done)

    for row in videos:
        if limit and processed_count >= limit:
            break
        vid = row["video_id"]
        if vid in done:
            continue
        try:
            meta = fetch_meta(vid, row["url"])
            transcript_text, transcript_file = fetch_caption_from_meta(vid, meta)
            descr = clean_text(meta.get("description", ""))
            summary, tx_status, confidence = heuristic_summary(row.get("title", ""), descr, transcript_text)
            result = {
                "video_id": vid,
                "title": row.get("title"),
                "upload_date": row.get("upload_date"),
                "url": row.get("url"),
                "duration": meta.get("duration"),
                "view_count": meta.get("view_count"),
                "like_count": meta.get("like_count"),
                "transcript_status": tx_status,
                "transcript_file": transcript_file,
                "transcript_excerpt": transcript_text[:800] if transcript_text else "",
                "summary": summary,
                "confidence": confidence,
                "method": "title+description+captions_heuristic" if transcript_text else "title+description_heuristic",
            }
        except Exception as e:
            result = {
                "video_id": vid,
                "title": row.get("title"),
                "upload_date": row.get("upload_date"),
                "url": row.get("url"),
                "transcript_status": "missing",
                "confidence": "low",
                "summary": "Failed to fetch metadata/transcript in this run; retry needed.",
                "error": {"kind": "fetch_error", "message": str(e)},
            }

        append_result(result)
        md = [
            f"# {result['title']}",
            "",
            f"- Video ID: `{vid}`",
            f"- Date: {result.get('upload_date')}",
            f"- URL: {result.get('url')}",
            f"- Transcript: {result['transcript_status']} ({result.get('transcript_file') or 'none'})",
            f"- Confidence: {result['confidence']}",
            "",
            "## Strategy Summary",
            result["summary"],
            "",
            "## Notes",
            "- Summary uses available metadata and caption text when available.",
            "- Missing transcript/captions => lower confidence and title/description-only inference.",
        ]
        (KNOW_DIR / f"{vid}.md").write_text("\n".join(md))

        processed_count += 1
        write_checkpoint(processed_count, len(videos))

    print(f"Summaries complete. Processed total: {processed_count}/{len(videos)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Stop once total processed reaches this number")
    parser.add_argument("--force-rebuild", action="store_true", help="Rebuild summaries from scratch")
    args = parser.parse_args()
    main(limit=args.limit, force_rebuild=args.force_rebuild)
