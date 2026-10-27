"""Ground the 1,091 fixed-30s windows using overlapping human keystep annotations.

Phase 2 Step 1: Content-grounded window re-indexing.
Reads existing manual keysteps from PostgreSQL in RAM, synthesizes authentic
captions for overlapping 30s windows, re-embeds them via the local BGE-M3
microservice on RTX 4050 GPU, and updates vec_segment_text in PostgreSQL.
Zero monetary spending ($0.00), zero disk clutter.
"""

import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.embeddings import BgeM3Client
from app.models import Asset, Segment
from app.search import index_segment_vector

BATCH_SIZE = 16


def run_reindex():
    print("=" * 70, flush=True)
    print("  TRACE — PHASE 2 STEP 1: CONTENT-GROUNDED WINDOW RE-INDEXING", flush=True)
    print("=" * 70, flush=True)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    endpoint = "http://127.0.0.1:8001/v1/embeddings"
    print(f"Connecting to local BGE-M3 microservice at {endpoint}...", flush=True)
    embedder = BgeM3Client(endpoint=endpoint)

    t_start = time.perf_counter()
    total_assets = 0
    total_windows = 0
    windows_with_keysteps = 0
    windows_idle = 0
    windows_to_embed: list[tuple[str, str]] = []  # (segment_id, caption)

    with session_maker() as session:
        assets = session.scalars(select(Asset).order_by(Asset.title)).all()
        total_assets = len(assets)
        print(f"Loaded {total_assets} assets from PostgreSQL.", flush=True)

        for asset in assets:
            manual_segs = session.scalars(
                select(Segment)
                .where(Segment.asset_id == asset.id, Segment.method == "manual")
                .order_by(Segment.start_s)
            ).all()

            windows = session.scalars(
                select(Segment)
                .where(Segment.asset_id == asset.id, Segment.method == "fixed-30s")
                .order_by(Segment.start_s)
            ).all()

            for win in windows:
                # Find overlapping manual keysteps
                overlapping = [
                    m
                    for m in manual_segs
                    if max(m.start_s, win.start_s) < min(m.end_s, win.end_s)
                ]

                # Aggregate unique action labels preserving sequence
                labels = []
                for m in overlapping:
                    txt = (m.caption or m.human_caption or "").strip()
                    if txt and txt not in labels:
                        labels.append(txt)

                if labels:
                    caption = (
                        f"{asset.title} [{win.start_s:.0f}s–{win.end_s:.0f}s]: "
                        + "; ".join(labels)
                    )
                    windows_with_keysteps += 1
                else:
                    caption = (
                        f"{asset.title} [{win.start_s:.0f}s–{win.end_s:.0f}s]: "
                        f"equipment setup and idle transition"
                    )
                    windows_idle += 1

                win.caption = caption
                windows_to_embed.append((win.id, caption))
                total_windows += 1

        session.commit()
        print(
            f"Updated captions for {total_windows} windows across {total_assets} assets.\n"
            f"  - Windows overlapping human keysteps: {windows_with_keysteps} "
            f"({windows_with_keysteps / total_windows * 100:.1f}%)\n"
            f"  - Windows during idle/transition:     {windows_idle} "
            f"({windows_idle / total_windows * 100:.1f}%)",
            flush=True,
        )

        # Batch embedding and pgvector update
        print(f"\nGenerating 1024-d BGE-M3 embeddings on local GPU for {len(windows_to_embed)} windows...", flush=True)
        embedded_count = 0
        t_embed_start = time.perf_counter()

        for batch_start in range(0, len(windows_to_embed), BATCH_SIZE):
            batch = windows_to_embed[batch_start : batch_start + BATCH_SIZE]
            texts = [item[1] for item in batch]

            resp = embedder.embed(texts)
            vectors = resp.vectors

            for (seg_id, _), vec in zip(batch, vectors, strict=True):
                index_segment_vector(session, seg_id, vec)

            embedded_count += len(batch)
            if embedded_count % 160 == 0 or embedded_count == len(windows_to_embed):
                pct = embedded_count / len(windows_to_embed) * 100
                rate = embedded_count / max(0.001, time.perf_counter() - t_embed_start)
                print(
                    f"  Embedded & indexed {embedded_count:4d}/{len(windows_to_embed)} windows "
                    f"({pct:5.1f}%) — {rate:.1f} seg/s",
                    flush=True,
                )

        session.commit()

    total_time = time.perf_counter() - t_start
    print("=" * 70, flush=True)
    print(
        f"SUCCESS: Re-indexed {total_windows} windows ({windows_with_keysteps} grounded) "
        f"in {total_time:.1f}s on local RTX 4050 GPU.",
        flush=True,
    )
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_reindex()
