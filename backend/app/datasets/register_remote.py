"""Audit an IndEgo verification report and register provenance in PostgreSQL.

No video, narration, labels, or frame pixels are persisted. Fetch current public
metadata and pinned annotations in RAM before opening the write transaction.
"""

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.datasets.indego import REPO, REVISION, discover, read_annotations, resolve, trial_group
from app.db import make_engine
from app.models import RemoteSource


def load_report(path):
    with Path(path).open("rb") as stream:
        payload = stream.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise ValueError("verification report exceeds 2 MiB")
    records = [json.loads(line) for line in payload.decode("utf-8-sig").splitlines() if line]
    catalogs = [r for r in records if r.get("event") == "catalog"]
    summaries = [r for r in records if r.get("event") == "summary"]
    if len(catalogs) != 1 or catalogs[0].get("revision") != REVISION:
        raise ValueError("report must contain exactly one matching pinned revision")
    if len(summaries) != 1 or records[-1] != summaries[0]:
        raise ValueError("report is incomplete or contains multiple runs")
    verified = [r for r in records if r.get("event") == "verified"]
    if not 20 <= len(verified) <= 25 or summaries[0].get("selected") != len(verified):
        raise ValueError("report must verify 20–25 selected videos")
    if summaries[0].get("decoded") is not True:
        raise ValueError("report did not decode video frames")
    paths, groups = set(), set()
    for record in verified:
        path = record["path"]
        duration = record["duration_s"]
        if not isinstance(duration, (float, int)) or not math.isfinite(duration):
            raise ValueError("invalid duration")
        if not 120 <= duration <= 900:
            raise ValueError("video violates original 2–15 minute scope")
        if record.get("decoded") is not True or len(record.get("frames", [])) != 3:
            raise ValueError("missing decoded-frame evidence")
        for frame, fraction in zip(record["frames"], (0.05, 0.5, 0.95), strict=True):
            if not re.fullmatch(r"[a-f0-9]{64}", frame.get("sha256", "")):
                raise ValueError("invalid frame hash")
            if (
                not math.isfinite(frame["timestamp_s"])
                or abs(frame["timestamp_s"] - duration * fraction) > 0.002
            ):
                raise ValueError("invalid frame timestamp")
        if path in paths or record["trial_group"] in groups:
            raise ValueError("duplicate source or trial group")
        if record["trial_group"] != trial_group(Path(path).name):
            raise ValueError("inconsistent trial group")
        paths.add(path)
        groups.add(record["trial_group"])
    duration = sum(r["duration_s"] for r in verified)
    if duration > 21600 or abs(duration - summaries[0]["duration_total_s"]) > 0.01:
        raise ValueError("invalid total duration")
    return verified, hashlib.sha256(payload).hexdigest()


def prepare(path):
    verified, report_hash = load_report(path)
    candidates, _ = discover("all")  # current gate/terms, pinned catalog and narration
    candidates = {c["path"]: c for c in candidates}
    values = []
    for record in verified:
        candidate = candidates.get(record["path"])
        if candidate is None:
            raise ValueError("verified source absent from pinned catalog")
        for key in ("size", "annotation_path", "trial_group"):
            if record[key] != candidate[key]:
                raise ValueError(f"catalog mismatch: {key}")
        narration_hash = hashlib.sha256(candidate["narration"].encode()).hexdigest()
        if narration_hash != record["narration_sha256"]:
            raise ValueError("narration changed")
        annotations = read_annotations(candidate)
        if len(annotations) != record["annotation_intervals"] or any(
            a["end_s"] > record["duration_s"] + 0.1 for a in annotations
        ):
            raise ValueError("annotation count or bounds mismatch")
        annotation_hash = hashlib.sha256(
            json.dumps(annotations, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        url = resolve(record["path"])
        values.append(
            {
                "id": str(uuid5(NAMESPACE_URL, url)),
                "repo": REPO,
                "revision": REVISION,
                "path": record["path"],
                "source_uri": url,
                "license": "CC-BY-4.0",
                "category": "assembly" if record["path"].startswith("1_Assembly/") else "repair",
                "duration_s": record["duration_s"],
                "trial_group": record["trial_group"],
                "verification": {
                    "report_sha256": report_hash,
                    "video_bytes": record["size"],
                    "annotation_path": record["annotation_path"],
                    "annotation_intervals": len(annotations),
                    "annotation_sha256": annotation_hash,
                    "narration_sha256": narration_hash,
                    "frame_checks": record["frames"],
                    "media_checksum_verified": False,
                    "human_verified": False,
                    "split": "unassigned",
                    "equipment_family": "unreviewed",
                    "trial_group_method": "filename heuristic; needs human review",
                    "attribution_url": f"https://huggingface.co/datasets/{REPO}",
                },
            }
        )
    return values


def register_sources(session, values):
    # Serialize registration, enforce corpus cap, and never overwrite prior provenance.
    session.execute(text("SELECT pg_advisory_xact_lock(72412024)"))
    existing = {s.source_uri: s for s in session.scalars(select(RemoteSource))}
    incoming = {v["source_uri"] for v in values}
    if len(incoming) != len(values) or len(set(existing) | incoming) > 25:
        raise ValueError("duplicate input or remote selection exceeds 25-video cap")
    created = 0
    for value in values:
        prior = existing.get(value["source_uri"])
        if prior:
            if any(getattr(prior, key) != item for key, item in value.items()):
                raise ValueError("existing source differs; explicit review required")
        else:
            session.add(RemoteSource(**value))
            created += 1
    session.flush()
    return {"created": created, "unchanged": len(values) - created, "total_selected": len(values)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--commit", action="store_true")
    args = parser.parse_args()
    values = prepare(args.report)
    result = {"validated_sources": len(values), "duration_s": sum(v["duration_s"] for v in values)}
    if args.commit:
        engine = make_engine(Settings())
        try:
            with Session(engine) as session, session.begin():
                result.update(register_sources(session, values))
        finally:
            engine.dispose()
    print(json.dumps({**result, "committed": args.commit, "media_files_written": 0}))


if __name__ == "__main__":
    main()
