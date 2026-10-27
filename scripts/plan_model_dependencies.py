"""Read registry JSON/headers only; never fetch wheels or install packages.

Produces a Windows CPython 3.12 candidate lock. This bounded resolver is for
planning, not a replacement for pip's resolver or a compatibility test.
"""

import json
import urllib.request
from pathlib import Path

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import InvalidVersion, Version

ROOT = Path(__file__).resolve().parents[1]
ENV = default_environment() | {
    "python_version": "3.12",
    "python_full_version": "3.12.0",
    "sys_platform": "win32",
    "platform_system": "Windows",
    "platform_machine": "AMD64",
    "os_name": "nt",
    "extra": "",
}
TAGS = set(cpython_tags((3, 12), platforms=["win_amd64"])) | set(
    compatible_tags((3, 12), interpreter="cp312", platforms=["win_amd64"])
)
CACHE = {}


def read(url):
    if url not in CACHE:
        with urllib.request.urlopen(url, timeout=25) as response:
            CACHE[url] = json.load(response)
    return CACHE[url]


def requirements(lines):
    result = []
    for line in lines:
        req = Requirement(line)
        if req.marker is None or req.marker.evaluate(ENV):
            if req.extras or req.url:
                raise ValueError(f"Manual review required for {req}")
            result.append(req)
    return result


def select(name, constraints):
    catalog = read(f"https://pypi.org/pypi/{name}/json")
    versions = []
    for label in catalog["releases"]:
        try:
            version = Version(label)
        except InvalidVersion:
            continue
        if not version.is_prerelease:
            versions.append(version)
    versions.sort(reverse=True)
    for version in versions:
        if not all(version in r.specifier for r in constraints):
            continue
        for wheel in catalog["releases"][str(version)]:
            if wheel["yanked"] or not wheel["filename"].endswith(".whl"):
                continue
            if not parse_wheel_filename(wheel["filename"])[3] & TAGS:
                continue
            if wheel.get("requires_python"):
                from packaging.specifiers import SpecifierSet

                if Version("3.12.0") not in SpecifierSet(wheel["requires_python"]):
                    continue
            metadata = read(f"https://pypi.org/pypi/{name}/{version}/json")
            return {
                "name": name,
                "version": str(version),
                "bytes": wheel["size"],
                "url": wheel["url"],
                "sha256": wheel["digests"]["sha256"],
                "requires_dist": metadata["info"].get("requires_dist") or [],
            }
    raise ValueError(f"No compatible binary for {name}: {constraints}")


def main():
    torch = json.loads((ROOT / "docs/verification/torch-wheel-metadata.json").read_text())
    roots = requirements(
        [
            "transformers==5.17.0",
            *[
                s.removeprefix("Requires-Dist: ")
                for s in torch["metadata"].splitlines()
                if s.startswith("Requires-Dist: ")
            ],
        ]
    )
    selected = {}
    for _ in range(20):
        constraints = {}
        pending = roots[:]
        visited = set()
        while pending:
            req = pending.pop()
            name = canonicalize_name(req.name)
            constraints.setdefault(name, []).append(req)
            if name in selected and name not in visited:
                visited.add(name)
                pending.extend(requirements(selected[name]["requires_dist"]))
        updated = {name: select(name, reqs) for name, reqs in constraints.items()}
        if updated == selected:
            break
        selected = updated
    else:
        raise RuntimeError("Resolution did not converge; manual review required")
    rows = sorted(selected.values(), key=lambda r: r["name"])
    output = {
        "target": "CPython 3.12 Windows AMD64",
        "status": "metadata-only candidate",
        "torch": {k: torch[k] for k in ["url", "bytes"]},
        "packages": rows,
        "software_bytes": torch["bytes"] + sum(r["bytes"] for r in rows),
    }
    (ROOT / "docs/verification/model-dependency-manifest.json").write_text(
        json.dumps(output, indent=2), encoding="utf-8"
    )
    print(json.dumps({"software_bytes": output["software_bytes"], "packages": len(rows)}))


if __name__ == "__main__":
    main()
