import json
import time
import urllib.request
import urllib.error

def test_query(query: str, link_expansion: bool = True):
    url = "http://localhost:8000/api/v1/search"
    payload = {
        "query": query,
        "modality": "all",
        "limit": 5,
        "link_expansion": link_expansion,
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            raw = resp.read().decode("utf-8")
            status_code = resp.status
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        status_code = e.code
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"\n{'='*70}")
    print(f"QUERY: '{query}' (Link Expansion: {link_expansion})")
    print(f"Status: {status_code} | Total Latency: {latency_ms:.1f} ms")
    print(f"{'='*70}")

    if status_code != 200:
        print("ERROR:", raw)
        return

    data = json.loads(raw)
    segs = data.get("video_segments", [])
    chunks = data.get("document_chunks", [])

    print(f"Retrieved {len(segs)} video segments:")
    for idx, s in enumerate(segs, start=1):
        via = " [VIA LINK]" if s.get("via_link") else ""
        rel = f" (rel: {s.get('link_relation')})" if s.get("link_relation") else ""
        print(f"  {idx}. [{s.get('asset_title')}] ({s.get('start_s'):.1f}s - {s.get('end_s'):.1f}s) seek={s.get('seek_to_s'):.1f}s score={s.get('score'):.4f}{via}{rel}")
        print(f"     caption: {s.get('caption')}")

    print(f"\nRetrieved {len(chunks)} document chunks:")
    for idx, c in enumerate(chunks, start=1):
        via = " [VIA LINK]" if c.get("via_link") else ""
        rel = f" (rel: {c.get('link_relation')})" if c.get("link_relation") else ""
        print(f"  {idx}. [{c.get('asset_title')} > {c.get('section_path')}] score={c.get('score'):.4f}{via}{rel}")
        print(f"     text: {c.get('text')[:100]}...")

def main():
    test_query("assemble lower hinge bracket", link_expansion=True)
    test_query("camera mounting plate fasteners", link_expansion=True)
    test_query("hydraulic pump pressure loss inspection", link_expansion=True)

if __name__ == "__main__":
    main()
