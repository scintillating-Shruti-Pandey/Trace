import io
import json
from urllib.error import HTTPError

import pytest
from app.datasets import huggingface as hf


class Response(io.BytesIO):
    def __init__(self, content, length=None):
        super().__init__(content)
        self.headers = {} if length is None else {"Content-Length": str(length)}


def test_response_budget_checks_actual_bytes_without_content_length(monkeypatch):
    monkeypatch.setattr(hf, "urlopen", lambda *a, **k: Response(b"x" * 11))
    with pytest.raises(hf.RemoteAccessError, match="memory budget"):
        hf.read_json("https://huggingface.co/api/datasets/example", max_bytes=10)


def test_response_budget_rejects_known_oversized_file(monkeypatch):
    monkeypatch.setattr(hf, "urlopen", lambda *a, **k: Response(b"", length=11))
    with pytest.raises(hf.RemoteAccessError, match="memory budget"):
        hf.read_json("https://huggingface.co/api/datasets/example", max_bytes=10)


def test_http_errors_preserve_status_without_leaking_body(monkeypatch):
    def denied(*args, **kwargs):
        raise HTTPError("https://example.invalid", 401, "secret", {}, None)

    monkeypatch.setattr(hf, "urlopen", denied)
    with pytest.raises(hf.RemoteAccessError) as error:
        hf.read_json("https://huggingface.co/api/datasets/example")
    assert error.value.status == 401
    assert str(error.value) == "HTTP 401"


def test_gate_stops_before_row_requests(monkeypatch):
    monkeypatch.setattr(hf, "read_json", lambda *a, **k: {"gated": "manual"})
    monkeypatch.setattr(hf, "viewer_json", lambda *a, **k: pytest.fail("gate bypass"))
    with pytest.raises(hf.RemoteAccessError, match="approval"):
        list(hf.iter_rows("lovr", config="default", split="train"))


def test_pagination_is_bounded_and_leaves_media_as_references(monkeypatch):
    calls = []
    monkeypatch.setattr(hf, "read_json", lambda *a, **k: {"gated": False})

    def rows(endpoint, repo, **params):
        calls.append(params)
        return {
            "rows": [
                {
                    "row": {"id": i, "image": "https://example.invalid/image.jpg"},
                    "truncated_cells": [],
                }
                for i in range(params["offset"], params["offset"] + params["length"])
            ]
        }

    monkeypatch.setattr(hf, "viewer_json", rows)
    result = list(hf.iter_rows("lovr", config="default", split="train", limit=7, batch_size=5))
    assert [r["id"] for r in result] == list(range(7))
    assert [c["length"] for c in calls] == [5, 2]
    assert result[0]["image"].endswith(".jpg")


def test_truncated_viewer_rows_fail_explicitly(monkeypatch):
    monkeypatch.setattr(hf, "read_json", lambda *a, **k: {"gated": False})
    monkeypatch.setattr(
        hf,
        "viewer_json",
        lambda *a, **k: {"rows": [{"row": {"cap": "partial"}, "truncated_cells": [0]}]},
    )
    with pytest.raises(hf.RemoteAccessError, match="truncated"):
        list(hf.iter_rows("lovr", config="default", split="train"))


def test_annotations_pin_revision_and_never_fetch_media(monkeypatch):
    calls = []

    def request(url, **kwargs):
        calls.append(url)
        if "/api/" in url:
            return {
                "sha": "revision123",
                "gated": False,
                "siblings": [{"rfilename": "t2v.json", "size": 100}],
            }
        return [
            {"qry_text": "test", "src_video_path": "video.mp4", "answering_time_interval": [1, 2]}
        ]

    monkeypatch.setattr(hf, "read_json", request)
    result = hf.read_moment_annotations()
    assert result["revision"] == "revision123"
    assert calls[-1].endswith("/resolve/revision123/t2v.json")
    assert len(calls) == 2


def test_read_json_keeps_payload_in_memory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(hf, "urlopen", lambda *a, **k: Response(json.dumps({"rows": []}).encode()))
    assert hf.read_json("https://huggingface.co/api/datasets/example") == {"rows": []}
    assert list(tmp_path.iterdir()) == []
