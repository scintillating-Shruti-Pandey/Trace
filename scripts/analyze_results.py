"""Analyze verification results from the final run."""
import json

lines = [json.loads(l) for l in open("docs/verification/indego-final-2026-10-24.jsonl") if l.strip()]
catalog = [l for l in lines if l.get("event") == "catalog"][0]
verified = [l for l in lines if l.get("event") == "verified"]
skipped = [l for l in lines if l.get("event") == "skipped"]
failed = [l for l in lines if l.get("event") == "failure"]

print(f"Catalog: {catalog['videos_listed']} videos listed, {catalog['matched_candidates']} matched")
print(f"Excluded narrations: {len(catalog['excluded_narrations'])}")
print(f"\nResults: {len(verified)} verified, {len(skipped)} skipped, {len(failed)} failed")
print()

assembly = [v for v in verified if "Assembly" in v["path"]]
repair = [v for v in verified if "Repair" in v["path"]]
print(f"Assembly: {len(assembly)}, Repair: {len(repair)}")
print()

for v in verified:
    cat = "ASM" if "Assembly" in v["path"] else "REP"
    name = v["path"].split("/")[-1]
    dur = v.get("duration_s", 0)
    net = v.get("network_bytes", 0)
    segs = v["annotation_intervals"]
    group = v["trial_group"]
    print(f"  [{cat}] {name:50s} dur={dur:7.1f}s  net={net/1024/1024:5.1f}MB  segs={segs}  group={group}")

dur_total = sum(v.get("duration_s", 0) for v in verified)
net_total = sum(v.get("network_bytes", 0) for v in verified)
groups = set(v["trial_group"] for v in verified)
print(f"\nTotal duration: {dur_total:.0f}s = {dur_total/60:.1f} min = {dur_total/3600:.2f} hours")
print(f"Total network: {net_total/1024/1024:.1f} MB")
print(f"Unique trial groups: {len(groups)}")
print(f"Spec target: 20-25 videos, 3-5 hours, hard cap 6 hours")
print(f"Gap: need {20-len(verified)} to {25-len(verified)} more verified videos")
