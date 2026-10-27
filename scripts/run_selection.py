"""Run IndEgo selection with a live progress display."""
import json
import sys
import time

from app.datasets.indego import discover, inspect_candidate

TARGET = 25
MIN_S = 60
MAX_S = 900

print("=" * 60)
print("  IndEgo Video Selection — Target: 25 videos")
print("=" * 60)

candidates, catalog = discover("all")
total = catalog["matched_candidates"]
print(f"\n  Catalog: {catalog['videos_listed']} listed, {total} matched, "
      f"{len(catalog['excluded_narrations'])} excluded\n")

# Deduplicate by trial group
import hashlib
groups = set()
unique = []
for c in candidates:
    if c["trial_group"] not in groups:
        unique.append(c)
        groups.add(c["trial_group"])

print(f"  Unique trial groups: {len(unique)}")
print(f"  Duration filter: {MIN_S}–{MAX_S}s")
print("-" * 60)

verified, skipped, failed = [], [], []
duration_total = 0
start_time = time.time()

# Save raw JSONL to file
out = open("/tmp/selection.jsonl", "w")
out.write(json.dumps({"event": "catalog", "revision": "c822468b5e0c9c42ebbf2939d3be936c2b203704", **catalog}) + "\n")

for i, candidate in enumerate(unique):
    if len(verified) >= TARGET:
        break

    name = candidate["path"].split("/")[-1]
    cat = "ASM" if "Assembly" in candidate["path"] else "REP"
    elapsed = time.time() - start_time

    sys.stdout.write(f"\r  [{len(verified):2d}/{TARGET}] Checking #{i+1}/{len(unique)} [{cat}] {name[:40]:<40s} ")
    sys.stdout.flush()

    result = inspect_candidate(candidate, True, min_s=MIN_S, max_s=MAX_S)
    out.write(json.dumps(result) + "\n")
    out.flush()

    if result["event"] == "verified":
        dur = result.get("duration_s", 0)
        net = result.get("network_bytes", 0)
        if duration_total + dur > 6 * 3600:
            skipped.append(result)
            print(f"  ⚠ 6h cap")
            continue
        duration_total += dur
        verified.append(result)
        print(f"  ✓ {dur:.0f}s  {net/1024/1024:.1f}MB")
    elif result["event"] == "skipped":
        skipped.append(result)
        print(f"  – skip ({result.get('reason', '?')})")
    else:
        failed.append(result)
        print(f"  ✗ {result.get('error', '?')[:50]}")

elapsed = time.time() - start_time
print("\n" + "=" * 60)
print(f"  DONE in {elapsed:.0f}s ({elapsed/60:.1f} min)")
print(f"  Verified: {len(verified)}/{TARGET}")
print(f"  Skipped:  {len(skipped)}")
print(f"  Failed:   {len(failed)}")
print(f"  Total duration: {duration_total:.0f}s ({duration_total/60:.1f} min)")
print(f"  Total network:  {sum(v.get('network_bytes',0) for v in verified)/1024/1024:.1f} MB")
print("=" * 60)

# Write summary
summary = {
    "event": "summary",
    "requested": TARGET,
    "selected": len(verified),
    "failures": [{"path": f["path"], "error": f.get("error","")} for f in failed],
    "skipped_count": len(skipped),
    "duration_total_s": duration_total,
    "duration_bounds": [MIN_S, MAX_S],
    "decoded": True,
    "local_media_files_written": 0,
    "corpus_imported": False,
}
out.write(json.dumps(summary) + "\n")
out.close()
print(f"\n  Results saved to /tmp/selection.jsonl")
print(f"  Copy out with: docker cp trace-api-1:/tmp/selection.jsonl docs/verification/indego-expanded-2026-10-24.jsonl")
