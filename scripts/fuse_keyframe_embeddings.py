"""Multi-modal visual + semantic fusion for keyframe retrieval per Engineering Spec §6 (S8).

Spec S8: "image-index: frames + standalone images → SigLIP 2 + caption + OCR → vec_image"
Fuses the 1,152-d visual image features with the 1,152-d caption semantic features
in SigLIP 2's joint embedding space:
fused = normalize(0.5 * v_image + 0.5 * v_caption)

Zero monetary spending ($0.00), zero external download, executed purely in RAM and GPU.
"""

import math
import sys
import time
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from app.search import (
    index_image_vector,
    index_segment_visual_vector,
)
from app.vision import DIMENSIONS as VISUAL_DIMENSIONS, MODEL as VISUAL_MODEL, SiglipVisualClient
from sqlalchemy import text


def run_fuse():
    print("=" * 70, flush=True)
    print("  TRACE — PHASE 3: MULTI-MODAL KEYFRAME EMBEDDING FUSION (SPEC S8)", flush=True)
    print("=" * 70, flush=True)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    visual_client = SiglipVisualClient(endpoint=settings.visual_endpoint)

    t_start = time.perf_counter()

    with session_maker() as session:
        rows = session.execute(
            text(
                """
                SELECT
                    img.id AS image_id,
                    img.segment_id,
                    img.caption,
                    v.embedding
                FROM images img
                JOIN vec_image v ON v.image_id = img.id
                ORDER BY img.id
                """
            )
        ).mappings().all()

    total = len(rows)
    print(f"Loaded {total} keyframe vectors from PostgreSQL.", flush=True)
    if total == 0:
        print("No images found. Exiting.", flush=True)
        return

    # 1. Parse image vectors and collect captions
    img_vecs = []
    captions = []
    for r in rows:
        raw = r["embedding"]
        if isinstance(raw, str):
            v = [float(x) for x in raw.strip("[]").split(",")]
        else:
            v = list(raw)
        img_vecs.append(v)
        captions.append(r["caption"] or "industrial workpiece")

    # 2. Embed captions in batches with SigLIP 2 text embedder on GPU
    print(f"Embedding {total} captions with SigLIP 2 text embedder on GPU...", flush=True)
    t_cap_start = time.perf_counter()
    batch_size = 32
    cap_vecs = []
    for i in range(0, total, batch_size):
        chunk = captions[i : i + batch_size]
        res = visual_client.embed_texts(chunk)
        cap_vecs.extend(res.vectors)
    t_cap_end = time.perf_counter()
    print(f"Captions embedded in {t_cap_end - t_cap_start:.2f}s.", flush=True)

    # 3. Fuse 50% visual image + 50% caption semantics with L2 normalization
    print("Computing balanced multi-modal fusion (0.5 visual + 0.5 semantic)...", flush=True)
    fused_items = []
    for r, iv, cv in zip(rows, img_vecs, cap_vecs, strict=True):
        fused = [0.5 * x + 0.5 * y for x, y in zip(iv, cv)]
        norm = math.hypot(*fused)
        normalized = tuple(x / norm for x in fused)
        fused_items.append((str(r["image_id"]), str(r["segment_id"]), normalized))

    # 4. Update vec_image and vec_segment_visual in PostgreSQL
    print("Updating vec_image and vec_segment_visual in PostgreSQL...", flush=True)
    t_db_start = time.perf_counter()
    with session_maker() as session:
        for img_id, seg_id, vec in fused_items:
            index_image_vector(session, img_id, vec, model=VISUAL_MODEL)
            if seg_id:
                index_segment_visual_vector(session, seg_id, vec, model=VISUAL_MODEL)
        session.commit()
    t_db_end = time.perf_counter()
    print(f"Database update complete in {t_db_end - t_db_start:.2f}s.", flush=True)

    total_time = time.perf_counter() - t_start
    print("=" * 70, flush=True)
    print("  MULTI-MODAL FUSION COMPLETE:", flush=True)
    print(f"  - Keyframes Updated: {total}", flush=True)
    print(f"  - Total Elapsed Time: {total_time:.2f}s ({total/total_time:.1f} items/s)", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_fuse()
