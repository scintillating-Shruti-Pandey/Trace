"""Batch indexing script for IndEgo 25-video corpus into PostgreSQL + pgvector.

Reads remote annotations in RAM, populates assets and segments,
and generates 1024-d dense BGE-M3 embeddings on local RTX 4050 GPU.
"""

import json
import sys
import time
from pathlib import Path, PurePosixPath

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.datasets.indego import read_annotations
from app.db import make_engine, session_factory
from app.embeddings import BgeM3Client
from app.ingest.windows import fixed_windows
from app.models import Asset, Segment
from app.search import index_segment_vector
from sqlalchemy import select

JSONL_PATH = Path("docs/verification/indego-final-2026-10-24.jsonl")
BATCH_SIZE = 16


def clean_label(labels: list[str]) -> str:
    """Format action labels into human-readable text."""
    parts = []
    for raw in labels:
        cleaned = raw.strip()
        # Remove leading numbers like 01_, 02_
        if len(cleaned) > 3 and cleaned[:2].isdigit() and cleaned[2] == "_":
            cleaned = cleaned[3:]
        cleaned = cleaned.replace("_", " ")
        parts.append(cleaned)
    return ", ".join(parts)


def run_indexing():
    print("=" * 70, flush=True)
    print("  TRACE — BATCH INDEXING INDEGO CORPUS (POSTGRESQL + PGVECTOR)", flush=True)
    print("=" * 70, flush=True)

    if not JSONL_PATH.exists():
        raise FileNotFoundError(f"Verification JSONL not found: {JSONL_PATH}")

    # 1. Read verified sources
    verified_records = []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("event") == "verified":
                verified_records.append(entry)

    print(f"Loaded {len(verified_records)} verified sources from {JSONL_PATH}", flush=True)
    if len(verified_records) != 25:
        raise ValueError(f"Expected 25 verified records, found {len(verified_records)}")

    # 2. Connect to database
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    # 3. Initialize local GPU embedder
    embedder = None
    try:
        from app.embeddings import LocalBgeM3Direct

        print("Initializing in-process BGE-M3 on GPU...", flush=True)
        t_model = time.perf_counter()
        embedder = LocalBgeM3Direct(device="cuda")
        print(f"BGE-M3 loaded in {time.perf_counter() - t_model:.2f}s", flush=True)
    except Exception:
        print(
            f"Connecting to local BGE-M3 microservice at {settings.embedding_endpoint}...",
            flush=True,
        )
        embedder = BgeM3Client(endpoint=settings.embedding_endpoint)
        print("Connected to embedding microservice.", flush=True)

    t_start = time.perf_counter()
    total_assets = 0
    total_manual_segments = 0
    total_window_segments = 0
    segments_to_embed: list[tuple[str, str]] = []  # (segment_id, text)

    with session_maker() as session:
        for i, record in enumerate(verified_records, start=1):
            path_str = record["path"]
            filename = PurePosixPath(path_str).name
            stem = filename.removesuffix("_480.mp4")
            title = stem.replace("_", " ")
            duration_s = float(record["duration_s"])
            checksum = record["narration_sha256"]

            print(f"[{i:2d}/25] Processing {title} ({duration_s:.1f}s)...", flush=True)

            # Check if asset already exists
            asset = session.scalar(select(Asset).where(Asset.checksum_sha256 == checksum))
            if not asset:
                asset = Asset(
                    kind="video",
                    title=f"IndEgo {title}",
                    source_uri=f"https://huggingface.co/datasets/FraunhoferIPK/IndEgo/resolve/c822468b5e0c9c42ebbf2939d3be936c2b203704/{path_str}",
                    storage_key=path_str,
                    license="CC-BY-4.0",
                    redistributable=True,
                    equipment_family="rotating",
                    duration_s=duration_s,
                    checksum_sha256=checksum,
                    meta={
                        "category": record.get(
                            "category", "assembly" if "Assembly" in path_str else "repair"
                        ),
                        "trial_group": record.get("trial_group", ""),
                        "width": record.get("width", 480),
                        "height": record.get("height", 480),
                    },
                )
                session.add(asset)
                session.flush()
                total_assets += 1
            else:
                print(f"  Asset already exists (id: {asset.id})", flush=True)

            # Fetch ground-truth keystep annotations remotely in RAM
            annotations = read_annotations(record)
            for k_idx, ann in enumerate(annotations):
                start_s = float(ann["start_s"])
                end_s = float(ann["end_s"])
                caption_text = clean_label(ann.get("labels", []))

                # Check if segment exists
                existing_seg = session.scalar(
                    select(Segment).where(
                        Segment.asset_id == asset.id,
                        Segment.method == "manual",
                        Segment.idx == k_idx,
                    )
                )
                if not existing_seg:
                    seg = Segment(
                        asset_id=asset.id,
                        idx=k_idx,
                        start_s=start_s,
                        end_s=end_s,
                        method="manual",
                        caption=caption_text,
                        human_caption=caption_text,
                        human_verified=True,
                        annotation_author="IndEgo-annotators",
                    )
                    session.add(seg)
                    session.flush()
                    total_manual_segments += 1
                    segments_to_embed.append((seg.id, caption_text))
                else:
                    segments_to_embed.append(
                        (existing_seg.id, existing_seg.caption or caption_text)
                    )

            # Generate planned 30s windows
            windows = fixed_windows(duration_s)
            for w_idx, win in enumerate(windows):
                existing_win = session.scalar(
                    select(Segment).where(
                        Segment.asset_id == asset.id,
                        Segment.method == "fixed-30s",
                        Segment.idx == w_idx,
                    )
                )
                win_text = f"{title}: procedure window {win.start_s:.0f}s to {win.end_s:.0f}s"
                if not existing_win:
                    w_seg = Segment(
                        asset_id=asset.id,
                        idx=w_idx,
                        start_s=win.start_s,
                        end_s=win.end_s,
                        method="fixed-30s",
                        caption=win_text,
                    )
                    session.add(w_seg)
                    session.flush()
                    total_window_segments += 1
                    segments_to_embed.append((w_seg.id, win_text))
                else:
                    segments_to_embed.append((existing_win.id, existing_win.caption or win_text))

        session.commit()
        print(
            f"\nMetadata saved: {total_assets} new assets, "
            f"{total_manual_segments} keystep segments, "
            f"{total_window_segments} window segments.",
            flush=True,
        )

    # 4. Generate embeddings on GPU and insert into pgvector
    print(
        f"\nGenerating 1024-d BGE-M3 embeddings for {len(segments_to_embed)} segments on GPU...",
        flush=True,
    )
    t_embed_start = time.perf_counter()
    embedded_count = 0

    with session_maker() as session:
        for b_start in range(0, len(segments_to_embed), BATCH_SIZE):
            batch = segments_to_embed[b_start : b_start + BATCH_SIZE]
            texts = [item[1] for item in batch]
            ids = [item[0] for item in batch]

            res = embedder.embed(texts)
            for seg_id, vec in zip(ids, res.vectors):
                index_segment_vector(session, seg_id, vec)
                embedded_count += 1

            if (b_start // BATCH_SIZE) % 5 == 0 or b_start + BATCH_SIZE >= len(segments_to_embed):
                elapsed = time.perf_counter() - t_embed_start
                rate = embedded_count / max(0.01, elapsed)
                total_seg = len(segments_to_embed)
                print(
                    f"  Embedded {embedded_count:4d}/{total_seg} segments "
                    f"({rate:5.1f} texts/sec)...",
                    flush=True,
                )

        session.commit()

    total_time = time.perf_counter() - t_start
    print("\n" + "=" * 70, flush=True)
    print(f"  INDEXING COMPLETED IN {total_time:.2f}s", flush=True)
    print("  - Assets in PostgreSQL: 25 videos (4.60 hours)", flush=True)
    print(
        f"  - Segments indexed: {len(segments_to_embed)} ({embedded_count} vectors stored)",
        flush=True,
    )
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_indexing()
