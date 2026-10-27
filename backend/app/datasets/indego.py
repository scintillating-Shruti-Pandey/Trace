"""Pinned IndEgo repair-video access and validation; summaries only are persisted.

Run inside the existing API image for ffmpeg/ffprobe. This does not ingest assets,
create benchmark splits, generate captions, or replace the deferred MinIO pipeline.
"""

import argparse
import hashlib
import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import PurePosixPath
from urllib.parse import quote

from app.datasets.huggingface import HUB, RemoteAccessError, read_json
from app.datasets.remote_video import RemoteObject, verify_video

REPO = "FraunhoferIPK/IndEgo"
REVISION = "c822468b5e0c9c42ebbf2939d3be936c2b203704"
CATEGORIES = {
    "repair": (
        "2_Inspection_Repair",
        "annotated_keysteps_inspection_repair",
        "narration_transcript_inspection_repair.json",
    ),
    "assembly": (
        "1_Assembly",
        "annotated_keysteps_assembly_disassembly",
        "narration_transcript_assembly.json",
    ),
}


def resolve(path):
    if PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        raise ValueError("invalid repository path")
    return f"{HUB}/datasets/{REPO}/resolve/{REVISION}/{quote(path, safe='/')}"


def trial_group(filename):
    """Conservative filename grouping only, not verified participant-independent splits."""
    stem = filename.removesuffix("_480.mp4")
    return re.sub(r"^(?:User_?\d+_)+", "", stem)


def directory(path):
    rows = read_json(f"{HUB}/api/datasets/{REPO}/tree/{REVISION}/{path}?limit=1000")
    if not isinstance(rows, list) or len(rows) >= 1000:
        raise RemoteAccessError("directory schema or pagination needs review")
    return rows


def discover(category="repair"):
    if category == "all":
        results = [discover(name) for name in CATEGORIES]
        candidates = [c for items, _ in results for c in items]
        candidates.sort(key=lambda x: hashlib.sha256(("trace-42:" + x["path"]).encode()).digest())
        return candidates, {
            "videos_listed": sum(summary["videos_listed"] for _, summary in results),
            "matched_candidates": len(candidates),
            "categories": list(CATEGORIES),
            "excluded_narrations": [
                item for _, summary in results for item in summary["excluded_narrations"]
            ],
        }
    root, annotation_dir, narration_file = CATEGORIES[category]
    info = read_json(f"{HUB}/api/datasets/{REPO}?expand[]=gated&expand[]=cardData")
    if info.get("gated"):
        raise RemoteAccessError("repository access approval is required", status=403)
    if info.get("cardData", {}).get("license") != "cc-by-4.0":
        raise RemoteAccessError("dataset terms changed; review required")
    videos = [v for v in directory(f"{root}/mp4_480") if v["path"].endswith(".mp4")]
    annotations = {
        PurePosixPath(a["path"]).name.removeprefix("AS_").removesuffix(".json"): a["path"]
        for a in directory(f"{root}/{annotation_dir}")
        if a["path"].endswith(".json")
    }
    narration = read_json(resolve(f"{root}/{narration_file}"))
    transcripts = {}
    excluded = []
    for row in narration:
        name, transcript = row["name"], row["transcript"]
        if name in transcripts:
            raise RemoteAccessError("duplicate narration; review required")
        if not isinstance(transcript, str) or not transcript.strip():
            excluded.append({"name": name, "reason": "empty narration"})
            continue
        transcripts[name] = transcript
    candidates = []
    for video in videos:
        name = PurePosixPath(video["path"]).name
        stem = name.removesuffix("_480.mp4")
        if name in transcripts and stem in annotations:
            candidates.append(
                {
                    "path": video["path"],
                    "size": video["size"],
                    "annotation_path": annotations[stem],
                    "trial_group": trial_group(name),
                    "narration": transcripts[name],
                }
            )
    # Reproducible ordering independent of file size; no claim of stratified sampling.
    candidates.sort(key=lambda x: hashlib.sha256(("trace-42:" + x["path"]).encode()).digest())
    return candidates, {
        "videos_listed": len(videos),
        "matched_candidates": len(candidates),
        "excluded_narrations": excluded,
    }


def read_annotations(candidate):
    data = read_json(resolve(candidate["annotation_path"]))
    name = PurePosixPath(candidate["path"]).name
    files = data.get("file", {})
    if len(files) != 1 or next(iter(files.values())).get("fname") != name:
        raise RemoteAccessError("annotation does not reference exactly the selected video")
    expected_fid = str(next(iter(files)))
    segments = []
    for item in data.get("metadata", {}).values():
        bounds = item.get("z", [])
        if (
            len(bounds) != 2
            or not all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in bounds
            )
            or not 0 <= bounds[0] < bounds[1]
        ):
            raise RemoteAccessError("invalid annotation interval")
        view = data.get("view", {}).get(str(item.get("vid")), {})
        if [str(v) for v in view.get("fid_list", [])] != [expected_fid]:
            raise RemoteAccessError("annotation view points to a different video")
        labels = []
        for key, value in item.get("av", {}).items():
            options = data.get("attribute", {}).get(key, {}).get("options", {})
            labels.append(options.get(str(value), str(value)))
        if not labels or not all(labels):
            raise RemoteAccessError("annotation label is empty")
        segments.append({"start_s": bounds[0], "end_s": bounds[1], "labels": labels})
    if not segments:
        raise RemoteAccessError("no temporal annotations")
    return segments


def inspect_candidate(candidate, decode, *, min_s=120, max_s=900):
    summary = {k: v for k, v in candidate.items() if k != "narration"}
    summary["narration_sha256"] = hashlib.sha256(candidate["narration"].encode()).hexdigest()
    try:
        segments = read_annotations(candidate)
        last_end = max(s["end_s"] for s in segments)
        if not min_s <= last_end <= max_s:
            return {"event": "skipped", "path": candidate["path"], "reason": "duration scope"}
        summary.update(annotation_intervals=len(segments), last_annotation_end_s=last_end)
        if decode:
            summary.update(verify_video(resolve(candidate["path"]), candidate["size"]))
            if last_end > summary["duration_s"] + 0.1:
                raise RemoteAccessError("annotation exceeds measured video duration")
            if not min_s <= summary["duration_s"] <= max_s:
                raise RemoteAccessError("measured video duration outside scope")
        else:
            source = RemoteObject(resolve(candidate["path"]), candidate["size"])
            prefix = source.block(0)
            if prefix[4:8] != b"ftyp":
                raise RemoteAccessError("media prefix is not an MP4 header")
            summary.update(network_bytes=source.bytes_read, range_requests=source.requests)
        summary["decoded"] = decode
        return {"event": "verified", **summary}
    except (RemoteAccessError, KeyError, TypeError, ValueError) as exc:
        return {"event": "failure", "path": candidate["path"], "error": str(exc)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--category", choices=[*CATEGORIES, "all"], default="all")
    parser.add_argument("--workers", type=int, choices=[1, 2, 3], default=1)
    parser.add_argument(
        "--decode", action="store_true", help="decode three frames per selected video"
    )
    parser.add_argument("--min-duration", type=int, default=120, help="minimum seconds")
    parser.add_argument("--max-duration", type=int, default=900, help="maximum seconds")
    args = parser.parse_args()
    if not 1 <= args.limit <= 25:
        parser.error("limit must be between 1 and 25")
    if not 30 <= args.min_duration < args.max_duration <= 3600:
        parser.error("duration bounds must satisfy 30 <= min < max <= 3600")
    try:
        candidates, catalog = discover(args.category)
    except (RemoteAccessError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"event": "fatal", "error": str(exc)}), flush=True)
        return 1
    print(json.dumps({"event": "catalog", "revision": REVISION, **catalog}), flush=True)
    groups, selected, failures, skipped = set(), [], [], []
    unique = []
    for candidate in candidates:
        if candidate["trial_group"] not in groups:
            unique.append(candidate)
            groups.add(candidate["trial_group"])
    remaining = iter(unique)
    duration_total = 0
    min_s, max_s = args.min_duration, args.max_duration
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        while len(selected) < args.limit:
            batch = []
            for _ in range(min(args.workers, args.limit - len(selected))):
                candidate = next(remaining, None)
                if candidate is not None:
                    batch.append(candidate)
            if not batch:
                break
            # Ordered results keep selection reproducible despite concurrent HTTP reads.
            for summary in pool.map(
                lambda c: inspect_candidate(c, args.decode, min_s=min_s, max_s=max_s),
                batch,
            ):
                if summary["event"] == "failure":
                    failures.append(summary)
                elif summary["event"] == "skipped":
                    skipped.append(summary)
                else:
                    duration = summary.get("duration_s", summary["last_annotation_end_s"])
                    if duration_total + duration > 6 * 3600:
                        skipped.append({"path": summary["path"], "reason": "six-hour total cap"})
                        continue
                    duration_total += duration
                    selected.append(summary)
                print(json.dumps(summary), flush=True)
    print(
        json.dumps(
            {
                "event": "summary",
                "requested": args.limit,
                "selected": len(selected),
                "failures": failures,
                "skipped": skipped,
                "duration_total_s": duration_total,
                "duration_bounds": [min_s, max_s],
                "decoded": args.decode,
                "local_media_files_written": 0,
                "grouping": "filename heuristic; human trial/split review still required",
                "corpus_imported": False,
            }
        ),
        flush=True,
    )
    return 0 if len(selected) == args.limit else 1


if __name__ == "__main__":
    raise SystemExit(main())
