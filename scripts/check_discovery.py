"""Quick discovery check - run inside Docker container."""
import json
from app.datasets.indego import discover

candidates, summary = discover("all")
print(json.dumps({
    "total_candidates": summary["matched_candidates"],
    "videos_listed": summary["videos_listed"],
    "excluded": summary["excluded_narrations"],
    "categories": summary["categories"],
}, indent=2))

# Count how many pass duration scope (120-900s annotation end)
from app.datasets.indego import read_annotations
from app.datasets.huggingface import RemoteAccessError

in_scope = 0
out_scope = 0
for c in candidates[:30]:  # Check first 30 for quick stats
    try:
        segs = read_annotations(c)
        last_end = max(s["end_s"] for s in segs)
        if 120 <= last_end <= 900:
            in_scope += 1
        else:
            out_scope += 1
    except (RemoteAccessError, Exception) as e:
        print(json.dumps({"path": c["path"], "error": str(e)}))

print(json.dumps({"checked": 30, "in_scope": in_scope, "out_scope": out_scope}))
