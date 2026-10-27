"""Bounded public Hugging Face reads without dataset downloads or disk caching.

Only metadata and Viewer rows are accessed. Media URLs in rows are references, never
followed automatically. No datasets/hub cache is created by this module.
"""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REGISTRY = {
    "lovr": "debugger123/LoVR-benchmark",
    "inspecsafe": "Tetrabot2026/InspecSafe-V1",
    "momentseeker": "avery00/MomentSeeker",
}
HUB = "https://huggingface.co"
VIEWER = "https://datasets-server.huggingface.co"
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MOMENT_TASKS = {"text": "t2v.json", "text-image": "ti2v.json", "text-video": "tv2v.json"}


class RemoteAccessError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


def read_json(url, *, max_bytes=MAX_RESPONSE_BYTES):
    """Read a bounded response into RAM; never create a file or a cache."""
    if max_bytes < 1:
        raise ValueError("max_bytes must be positive")
    request = Request(url, headers={"User-Agent": "Trace-remote-datasets/0.1"})
    try:
        with urlopen(request, timeout=25) as response:
            size = response.headers.get("Content-Length")
            if size and int(size) > max_bytes:
                raise RemoteAccessError(f"response exceeds {max_bytes}-byte memory budget")
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise RemoteAccessError(f"response exceeds {max_bytes}-byte memory budget")
            return json.loads(body)
    except HTTPError as exc:
        # Do not expose response bodies or signed redirect URLs in logs.
        raise RemoteAccessError(f"HTTP {exc.code}", status=exc.code) from exc
    except (URLError, TimeoutError) as exc:
        raise RemoteAccessError("network request failed or timed out") from exc


def viewer_json(endpoint, repo, **params):
    return read_json(f"{VIEWER}/{endpoint}?{urlencode({'dataset': repo, **params})}")


def inspect_dataset(name):
    """Inspect catalog and Viewer support, without fetching media or dataset rows."""
    repo = REGISTRY[name]
    output = {"name": name, "repo": repo, "local_dataset_bytes": 0}
    try:
        info = read_json(f"{HUB}/api/datasets/{repo}?blobs=true")
        output.update(
            {
                "revision": info.get("sha"),
                "gated": info.get("gated"),
                "license": info.get("cardData", {}).get("license"),
                "files": [
                    {"path": item["rfilename"], "size": item.get("size")}
                    for item in info.get("siblings", [])
                ],
            }
        )
    except RemoteAccessError as exc:
        output["hub_error"] = {"message": str(exc), "status": exc.status}
    for endpoint in ("is-valid", "size", "splits"):
        try:
            output[endpoint] = viewer_json(endpoint, repo)
        except RemoteAccessError as exc:
            output[endpoint] = {"error": str(exc), "status": exc.status}
    return output


def iter_rows(name, *, config, split, limit=5, offset=0, batch_size=5):
    """Yield bounded Viewer rows on demand; the caller chooses whether to retain them.

    Explicit config and split avoid silently mixing benchmark train/test data.
    This is sequential access, not a random or stratified evaluation sample.
    """
    if not 1 <= limit <= 500 or not 1 <= batch_size <= 100 or offset < 0:
        raise ValueError("limit must be 1..500, batch_size 1..100, offset nonnegative")
    repo = REGISTRY[name]
    # Honor a repository access gate even if some preview metadata is public.
    info = read_json(f"{HUB}/api/datasets/{repo}")
    if info.get("gated"):
        raise RemoteAccessError("repository access approval is required", status=403)
    remaining = limit
    while remaining:
        length = min(remaining, batch_size)
        data = viewer_json("rows", repo, config=config, split=split, offset=offset, length=length)
        rows = data.get("rows", [])
        if not rows:
            return
        for item in rows[:remaining]:
            if item.get("truncated_cells"):
                raise RemoteAccessError("Viewer truncated a cell; full row access needs review")
            yield item["row"]
            remaining -= 1
        if len(rows) < length:
            return
        offset += len(rows)


def read_moment_annotations(task="text"):
    """Read one small JSON annotation table into RAM at an immutable Hub revision.

    Image/video fields remain paths. This does not fetch the associated media.
    Unlike Viewer rows, JSON requires reading the whole bounded annotation file.
    """
    filename = MOMENT_TASKS[task]
    repo = REGISTRY["momentseeker"]
    info = read_json(f"{HUB}/api/datasets/{repo}?blobs=true")
    if info.get("gated"):
        raise RemoteAccessError("repository access approval is required", status=403)
    entry = next((f for f in info.get("siblings", []) if f["rfilename"] == filename), None)
    if entry is None or not info.get("sha"):
        raise RemoteAccessError("expected annotation file or revision is absent")
    if entry.get("size", 0) > MAX_RESPONSE_BYTES:
        raise RemoteAccessError("annotation file exceeds the memory budget")
    data = read_json(f"{HUB}/datasets/{repo}/resolve/{info['sha']}/{filename}")
    if not isinstance(data, list) or not all(
        isinstance(item, dict)
        and {"qry_text", "src_video_path", "answering_time_interval"} <= item.keys()
        for item in data
    ):
        raise RemoteAccessError("annotation schema differs from the verified dataset")
    return {"revision": info["sha"], "file": filename, "rows": data}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("name", choices=[*REGISTRY, "all"])
    sample = sub.add_parser("sample", help="read rows into RAM and print only their schema")
    sample.add_argument("name", choices=REGISTRY)
    sample.add_argument("--config", required=True)
    sample.add_argument("--split", required=True)
    sample.add_argument("--limit", type=int, default=5)
    sample.add_argument("--offset", type=int, default=0)
    annotations = sub.add_parser("annotations", help="read MomentSeeker annotation JSON into RAM")
    annotations.add_argument("--task", choices=MOMENT_TASKS, default="text")
    args = parser.parse_args()
    if args.command == "inspect":
        names = REGISTRY if args.name == "all" else [args.name]
        for name in names:
            print(json.dumps(inspect_dataset(name), ensure_ascii=True), flush=True)
        return 0
    try:
        if args.command == "annotations":
            result = read_moment_annotations(args.task)
            print(
                json.dumps(
                    {
                        "revision": result["revision"],
                        "file": result["file"],
                        "rows_read_in_memory": len(result["rows"]),
                        "local_dataset_bytes": 0,
                        "media_fetched": False,
                    }
                )
            )
            return 0
        count, columns = 0, set()
        for row in iter_rows(
            args.name, config=args.config, split=args.split, limit=args.limit, offset=args.offset
        ):
            count += 1
            columns.update(row)
        print(
            json.dumps(
                {
                    "rows_read_in_memory": count,
                    "columns": sorted(columns),
                    "local_dataset_bytes": 0,
                    "media_fetched": False,
                }
            )
        )
        return 0
    except (RemoteAccessError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "local_dataset_bytes": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
