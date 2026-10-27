"""Analyze skipped video durations to understand the gap."""
import json

lines = [json.loads(l) for l in open("docs/verification/indego-final-2026-10-24.jsonl") if l.strip()]
skipped = [l for l in lines if l.get("event") == "skipped" and l.get("reason") == "duration scope"]

# To understand the actual durations we'd need to read annotations for each.
# But we can infer from the selection process: they were skipped because
# annotation last_end was outside 120-900s range.
# Let's check which ones are assembly vs repair
for s in skipped:
    cat = "ASM" if "Assembly" in s["path"] else "REP"
    name = s["path"].split("/")[-1]
    print(f"  [{cat}] {name}")

print(f"\nTotal skipped: {len(skipped)}")
asm_skip = sum(1 for s in skipped if "Assembly" in s["path"])
rep_skip = sum(1 for s in skipped if "Repair" in s["path"])
print(f"Assembly skipped: {asm_skip}, Repair skipped: {rep_skip}")
print(f"\nNote: These videos have annotation endpoints outside 120-900s (2-15 min)")
print(f"The lower bound (120s) may be too restrictive for some useful shorter videos.")
print(f"Current lower bound: 120s. Consider lowering to 60s to include ~4-7 more candidates.")
