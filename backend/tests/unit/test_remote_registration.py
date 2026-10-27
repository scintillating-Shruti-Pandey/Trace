import copy
import json
from pathlib import Path

import pytest
from app.datasets.register_remote import load_report

REPORT = Path(__file__).resolve().parents[3] / "docs/verification/indego-final-2026-10-24.jsonl"


def test_completed_report_meets_original_scope():
    records, digest = load_report(REPORT)
    assert len(records) == 25 and len(digest) == 64
    assert sum(r["annotation_intervals"] for r in records) == 114


@pytest.mark.parametrize("issue", ["short", "duplicate", "incomplete", "frame", "revision", "nan"])
def test_bad_verification_never_qualifies_for_registration(tmp_path, issue):
    rows = [json.loads(line) for line in REPORT.read_text(encoding="utf-8-sig").splitlines()]
    rows = copy.deepcopy(rows)
    verified = [r for r in rows if r["event"] == "verified"]
    if issue == "short":
        verified[0]["duration_s"] = 90
    elif issue == "duplicate":
        verified[1]["path"] = verified[0]["path"]
    elif issue == "incomplete":
        rows.pop()
    elif issue == "frame":
        verified[0]["frames"][0]["sha256"] = "not-a-hash"
    elif issue == "nan":
        verified[0]["frames"][0]["timestamp_s"] = float("nan")
    else:
        rows[0]["revision"] = "another-revision"
    report = tmp_path / "report.jsonl"
    report.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    with pytest.raises(ValueError):
        load_report(report)
