"""Small annotation client; all validation and persistence live in the API."""

import argparse
import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser(prog="trace")
    parser.add_argument("--api", default="http://localhost:8000")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("assets")
    for name in ("ingest", "link", "segment", "chunk", "verify"):
        command = sub.add_parser(name)
        command.add_argument("file", type=Path, help="JSON payload, see API /docs")
        if name in {"segment", "chunk", "verify"}:
            command.add_argument("id", help="asset ID, or segment ID for verify")
    job = sub.add_parser("job")
    job.add_argument("id")
    args = parser.parse_args()
    endpoint = {
        "status": "/status",
        "assets": "/assets",
        "ingest": "/ingest",
        "link": "/links",
        "segment": f"/assets/{getattr(args, 'id', '')}/segments",
        "chunk": f"/assets/{getattr(args, 'id', '')}/chunks",
        "verify": f"/segments/{getattr(args, 'id', '')}",
        "job": f"/ingest/{getattr(args, 'id', '')}",
    }[args.command]
    try:
        data = (
            json.dumps(json.loads(args.file.read_text(encoding="utf-8"))).encode()
            if hasattr(args, "file")
            else None
        )
        request = Request(
            args.api.rstrip("/") + "/api/v1" + endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PATCH" if args.command == "verify" else None,
        )
        with urlopen(request, timeout=30) as response:
            print(json.dumps(json.load(response), indent=2))
    except HTTPError as exc:
        print(exc.read().decode(), file=sys.stderr)
        return 1
    except (URLError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
