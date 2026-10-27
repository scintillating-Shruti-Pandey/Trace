import json

lines = [json.loads(l) for l in open("docs/verification/indego-expanded-2026-10-24.jsonl") if l.strip()]
verified = [l for l in lines if l.get("event") == "verified"]
summary = [l for l in lines if l.get("event") == "summary"][0]

asm = [v for v in verified if "Assembly" in v["path"]]
rep = [v for v in verified if "Repair" in v["path"]]
dur = sum(v["duration_s"] for v in verified)
net = sum(v["network_bytes"] for v in verified)
segs = sum(v["annotation_intervals"] for v in verified)

print(f"=== EXPANDED SELECTION RESULTS ===")
print(f"Selected: {len(verified)}/25")
print(f"Assembly: {len(asm)}, Repair: {len(rep)}")
print(f"Duration: {dur:.0f}s = {dur/60:.1f}min = {dur/3600:.2f}h")
print(f"Network:  {net/1024/1024:.1f} MB")
print(f"Segments: {segs} annotation intervals")
print(f"Failures: {len(summary['failures'])}")
print(f"Skipped:  {summary['skipped_count']}")
print(f"\nSpec check:")
print(f"  Videos: {len(verified)}/20-25 ✓")
print(f"  Duration: {dur/3600:.2f}h / 3-5h target, 6h cap ✓")
print(f"\nPer video:")
for v in verified:
    cat = "ASM" if "Assembly" in v["path"] else "REP"
    name = v["path"].split("/")[-1]
    print(f"  [{cat}] {name:50s} {v['duration_s']:7.1f}s  {v['network_bytes']/1024/1024:5.1f}MB  segs={v['annotation_intervals']}")
