import io
from urllib.request import Request, urlopen

import pytest
from app.datasets import indego
from app.datasets import remote_video as rv
from app.datasets.huggingface import RemoteAccessError


class Response(io.BytesIO):
    def __init__(self, data, status=206, content_range="bytes 0-9/10"):
        super().__init__(data)
        self.status = status
        self.headers = {"Content-Range": content_range}


@pytest.mark.parametrize("status,span", [(200, "bytes 0-9/10"), (206, "bytes 1-10/11")])
def test_rejects_ignored_or_misdirected_ranges(monkeypatch, status, span):
    monkeypatch.setattr(rv, "urlopen", lambda *a, **k: Response(b"x" * 10, status, span))
    with pytest.raises(RemoteAccessError, match="exact byte range"):
        rv.RemoteObject("https://example.invalid", 10).block(0)


def test_byte_budget_fails_before_network_request(monkeypatch):
    monkeypatch.setattr(rv, "urlopen", lambda *a, **k: pytest.fail("over-budget request"))
    with pytest.raises(RemoteAccessError, match="budget"):
        rv.RemoteObject("https://example.invalid", 10, budget=9).block(0)


def test_short_ranges_are_not_cached(monkeypatch):
    monkeypatch.setattr(rv, "urlopen", lambda *a, **k: Response(b"short"))
    obj = rv.RemoteObject("https://example.invalid", 10)
    with pytest.raises(RemoteAccessError, match="short media"):
        obj.block(0)
    assert obj.bytes_read == 5 and not obj.cache


def test_loopback_proxy_supports_seeking_without_files(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    obj = rv.RemoteObject("https://example.invalid", 10)
    monkeypatch.setattr(obj, "block", lambda index: b"0123456789")
    with rv.serve_object(obj) as url:
        with urlopen(Request(url, headers={"Range": "bytes=4-6"})) as response:
            assert response.status == 206
            assert response.headers["Content-Range"] == "bytes 4-6/10"
            assert response.read() == b"456"
    assert list(tmp_path.iterdir()) == []


def annotation(bounds=(1, 5), name="User_1_451_2401_1_480.mp4"):
    return {
        "file": {"1": {"fname": name}},
        "view": {"1": {"fid_list": ["1"]}},
        "attribute": {"1": {"options": {"0": "inspect"}}},
        "metadata": {"a": {"vid": "1", "z": list(bounds), "av": {"1": "0"}}},
    }


@pytest.mark.parametrize("bounds", [(2, 1), (-1, 5), (0, float("nan")), (0, float("inf"))])
def test_invalid_gold_timestamps_are_rejected(monkeypatch, bounds):
    monkeypatch.setattr(indego, "read_json", lambda *a, **k: annotation(bounds))
    with pytest.raises(RemoteAccessError, match="interval"):
        indego.read_annotations({"path": "User_1_451_2401_1_480.mp4", "annotation_path": "a"})


def test_annotation_names_and_labels_are_verified(monkeypatch):
    monkeypatch.setattr(indego, "read_json", lambda *a, **k: annotation())
    candidate = {"path": "User_1_451_2401_1_480.mp4", "annotation_path": "a"}
    assert indego.read_annotations(candidate)[0]["labels"] == ["inspect"]
    candidate["path"] = "unrelated.mp4"
    with pytest.raises(RemoteAccessError, match="selected video"):
        indego.read_annotations(candidate)


def test_paired_view_grouping_is_conservative():
    assert indego.trial_group("User_14_User_15_411_1010_1_480.mp4") == indego.trial_group(
        "User_15_User_14_411_1010_1_480.mp4"
    )
    assert indego.trial_group("User_14_411_1010_2_480.mp4") != "411_1010_1"


def test_gate_blocks_discovery_before_listing(monkeypatch):
    monkeypatch.setattr(indego, "read_json", lambda *a, **k: {"gated": "manual"})
    monkeypatch.setattr(indego, "directory", lambda *a: pytest.fail("gate bypass"))
    with pytest.raises(RemoteAccessError, match="approval"):
        indego.discover()


def test_empty_narrations_are_reported_and_excluded(monkeypatch):
    def read(url):
        if "/api/" in url:
            return {"gated": False, "cardData": {"license": "cc-by-4.0"}}
        return [
            {"name": "User_1_451_1_480.mp4", "transcript": "assembly narration"},
            {"name": "User_2_451_2_480.mp4", "transcript": " "},
        ]

    def directory(path):
        if path.endswith("mp4_480"):
            return [
                {"path": path + "/User_1_451_1_480.mp4", "size": 10},
                {"path": path + "/User_2_451_2_480.mp4", "size": 10},
            ]
        return [
            {"path": path + "/AS_User_1_451_1.json"},
            {"path": path + "/AS_User_2_451_2.json"},
        ]

    monkeypatch.setattr(indego, "read_json", read)
    monkeypatch.setattr(indego, "directory", directory)
    candidates, catalog = indego.discover("assembly")
    assert len(candidates) == 1
    assert catalog["excluded_narrations"] == [
        {"name": "User_2_451_2_480.mp4", "reason": "empty narration"}
    ]


def test_decoding_rejects_truncated_pixel_output(monkeypatch):
    import json
    from contextlib import contextmanager

    @contextmanager
    def proxy(_):
        yield "http://127.0.0.1/video.mp4"

    def decode(args):
        if args[0] == "ffprobe":
            return json.dumps(
                {"streams": [{"codec_type": "video"}], "format": {"duration": "200"}}
            ).encode()
        return b"incomplete pixels"

    monkeypatch.setattr(rv, "serve_object", proxy)
    monkeypatch.setattr(rv, "run_decoder", decode)
    with pytest.raises(RemoteAccessError, match="complete RGB frame"):
        rv.verify_video("https://example.invalid", 100)
