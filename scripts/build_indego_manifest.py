"""Verify the pinned IndEgo video sources and build the on-demand IVP manifest.

Run from any working directory with network access. This makes one 256-byte ranged
request per verified video, writes only source metadata to the manifest, and never
downloads or stores video payloads.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from pathlib import PurePosixPath
from urllib.error import HTTPError
from urllib.request import Request, urlopen

REPO = "FraunhoferIPK/IndEgo"
REV = "c822468b5e0c9c42ebbf2939d3be936c2b203704"
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/{REV}/"
ROOT = Path(__file__).resolve().parents[1]
JSONL = ROOT / "docs/verification/indego-final-2026-10-24.jsonl"
OUT = ROOT / "backend/app/static/indego_manifest.json"

with JSONL.open(encoding="utf-8") as handle:
    verified = [
        record
        for line in handle
        if line.strip()
        for record in [json.loads(line)]
        if record.get("event") == "verified"
    ]


def check(record):
    path = record["path"]
    url = BASE + path
    status = 0
    try:
        with urlopen(Request(url, headers={"Range": "bytes=0-255"}), timeout=90) as resp:
            status = resp.status
            resp.read()
    except HTTPError as exc:
        status = exc.code
    except Exception:  # noqa: BLE001
        status = -1
    stem = PurePosixPath(path).name.removesuffix("_480.mp4")
    category = "assembly" if path.startswith("1_Assembly") else "repair"
    return {
        "id": stem,
        "title": f"IndEgo {stem}",
        "stem": stem,
        "category": category,
        "path": path,
        "source_uri": url,
        "duration_s": round(float(record["duration_s"]), 2),
        "keysteps": int(record.get("annotation_intervals", 0)),
        "width": record.get("width", 480),
        "height": record.get("height", 480),
        "codec": record.get("codec", "h264"),
        "license": "CC-BY-4.0",
        "http_status": status,
    }


with ThreadPoolExecutor(max_workers=5) as pool:
    rows = list(pool.map(check, verified))

ok = [r for r in rows if r["http_status"] in (200, 206)]
print(f"reachable {len(ok)}/{len(rows)}")
for r in rows:
    if r["http_status"] not in (200, 206):
        print("  NOT OK", r["http_status"], r["stem"])

payload = {
    "dataset": REPO,
    "revision": REV,
    "license": "CC-BY-4.0",
    "verified_at": date.today().isoformat(),
    "total_videos": len(rows),
    "reachable_videos": len(ok),
    "total_duration_s": round(sum(r["duration_s"] for r in rows), 2),
    "videos": rows,
}
with open(OUT, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
print("wrote", OUT, "with", len(rows), "videos")
