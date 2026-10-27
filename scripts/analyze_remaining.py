"""Check remaining candidates and their annotation durations.

Reads the final verification log and identifies candidates that were 
skipped due to duration scope, then reads their actual annotation 
endpoints to determine if relaxing the lower bound would help.
"""
import json

lines = [json.loads(l) for l in open("docs/verification/indego-final-2026-10-24.jsonl") if l.strip()]

# Catalog shows 143 matched candidates, we processed some subset
verified = [l for l in lines if l.get("event") == "verified"]
skipped = [l for l in lines if l.get("event") == "skipped"]
failed = [l for l in lines if l.get("event") == "failure"]

# The run used --limit 25, so it tried to get 25 unique trial groups
# But the dedup + skipping means it examined more candidates than 25
examined = len(verified) + len(skipped) + len(failed)
print(f"Total lines examined (excl catalog): {examined}")
print(f"  Verified: {len(verified)}")
print(f"  Skipped: {len(skipped)}")
print(f"  Failed: {len(failed)}")

# How many more unique groups exist beyond those checked?
verified_groups = set(v["trial_group"] for v in verified)
print(f"\nVerified trial groups: {verified_groups}")
print(f"Count: {len(verified_groups)}")

# The selection algorithm deduplicates by trial_group before checking
# So skipped items represent groups that didn't pass the duration filter
# We need more groups that pass 120-900s OR we need to relax the filter

print(f"\nVerified duration range: {min(v['duration_s'] for v in verified):.0f}s - {max(v['duration_s'] for v in verified):.0f}s")
print(f"Verified annotation intervals: {sum(v['annotation_intervals'] for v in verified)} total")

# The total verified duration is 2.66 hours out of 6-hour cap
# Even with relaxed duration, we should be fine
remaining_budget = 6 * 3600 - sum(v["duration_s"] for v in verified)
print(f"\nRemaining 6-hour budget: {remaining_budget/60:.1f} min ({remaining_budget/3600:.2f} hours)")
print(f"Could fit ~{int(remaining_budget / 300)} more 5-min videos or ~{int(remaining_budget / 600)} more 10-min videos")
