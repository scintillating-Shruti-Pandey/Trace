"""Extract representative keyframes in memory for all 114 manual keysteps,
embed them with local SigLIP 2 (1,152-d) on the RTX 4050 GPU, and index into
PostgreSQL tables: images, vec_image, and vec_segment_visual.

Strictly adheres to:
- records/ENGINEERING_SPEC.md §7.1, §7.2, §8.3, §16.4
- Zero monetary spending ($0.00).
- Pure in-memory streaming: no media files or frame pixels persisted to disk.
- Pinned revision & source URIs from remote IndEgo dataset.
"""

import argparse
import base64
import concurrent.futures
import io
import math
import subprocess
import sys
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# Ensure backend is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Image, Segment
from app.search import (
    index_image_vector,
    index_segment_visual_vector,
)
from app.vision import DIMENSIONS as VISUAL_DIMENSIONS, MODEL as VISUAL_MODEL, SiglipVisualClient
from sqlalchemy import func, select, text


def extract_frame_bytes(source_uri: str, timestamp_s: float, timeout_s: float = 30.0) -> bytes:
    """Extract a single JPEG keyframe into memory using FFmpeg inside trace-api-1 container."""
    cmd = [
        "docker",
        "exec",
        "-i",
        "trace-api-1",
        "ffmpeg",
        "-v",
        "error",
        "-nostdin",
        "-ss",
        str(timestamp_s),
        "-i",
        source_uri,
        "-frames:v",
        "1",
        "-an",
        "-sn",
        "-f",
        "image2",
        "-vcodec",
        "mjpeg",
        "pipe:1",
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=timeout_s)
    if proc.returncode != 0 or len(proc.stdout) < 100:
        raise RuntimeError(
            f"FFmpeg extraction failed (code {proc.returncode}) for {source_uri} at {timestamp_s}s: {proc.stderr.decode()[:200]}"
        )
    return proc.stdout


def main():
    parser = argparse.ArgumentParser(description="Ingest keyframes for Phase 3 visual retrieval")
    parser.add_argument("--workers", type=int, default=4, help="Parallel worker threads for frame extraction")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for SigLIP 2 visual embedder")
    parser.add_argument("--endpoint", default="http://127.0.0.1:8002", help="SigLIP 2 visual service endpoint")
    args = parser.parse_args()

    print("=" * 70, flush=True)
    print("  TRACE — PHASE 3: KEYFRAME EXTRACTION & VISUAL INDEXING", flush=True)
    print("=" * 70, flush=True)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    visual_client = SiglipVisualClient(endpoint=args.endpoint)

    t_start = time.perf_counter()

    # 1. Fetch all manual keysteps from PostgreSQL
    with session_maker() as session:
        keystep_rows = session.execute(
            text(
                """
                SELECT
                    s.id AS segment_id,
                    s.asset_id,
                    s.idx,
                    s.start_s,
                    s.end_s,
                    s.caption,
                    a.source_uri,
                    a.title AS asset_title
                FROM segments s
                JOIN assets a ON a.id = s.asset_id
                WHERE s.method = 'manual'
                ORDER BY a.title, s.idx
                """
            )
        ).mappings().all()

    total_keysteps = len(keystep_rows)
    print(f"Loaded {total_keysteps} manual keysteps across IndEgo video corpus.", flush=True)
    if total_keysteps == 0:
        print("No manual keysteps found. Exiting.", flush=True)
        return

    # 2. Extract keyframes concurrently in memory
    print(f"Extracting keyframes in memory using {args.workers} workers (no disk persistence)...", flush=True)

    def process_item(row):
        seg_id = str(row["segment_id"])
        asset_id = str(row["asset_id"])
        start_s = float(row["start_s"])
        end_s = float(row["end_s"])
        timestamp_s = round((start_s + end_s) / 2.0, 3)
        caption = row["caption"] or ""
        source_uri = row["source_uri"]

        # Deterministic UUID for the image record
        image_id = str(uuid5(NAMESPACE_URL, f"keyframe:{seg_id}"))

        img_bytes = extract_frame_bytes(source_uri, timestamp_s)
        return {
            "image_id": image_id,
            "segment_id": seg_id,
            "asset_id": asset_id,
            "caption": caption,
            "storage_key": f"keyframes/{seg_id}.jpg",
            "img_bytes": img_bytes,
            "timestamp_s": timestamp_s,
        }

    extracted_items = []
    t_extract_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(process_item, row): row for row in keystep_rows}
        completed = 0
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            extracted_items.append(res)
            completed += 1
            if completed % 10 == 0 or completed == total_keysteps:
                print(f"  Extracted {completed}/{total_keysteps} keyframes ({len(res['img_bytes'])} bytes sample)...", flush=True)

    t_extract_end = time.perf_counter()
    print(f"Keyframe extraction complete: {len(extracted_items)} frames in {t_extract_end - t_extract_start:.2f}s.", flush=True)

    # 3. Batch embed keyframes and captions with SigLIP 2 on GPU per Spec §6 (S8)
    print(f"Embedding keyframes and captions with SigLIP 2 ({VISUAL_MODEL}, dim={VISUAL_DIMENSIONS})...", flush=True)
    t_embed_start = time.perf_counter()

    batch_size = args.batch_size
    embeddings_by_id = {}

    for i in range(0, len(extracted_items), batch_size):
        chunk = extracted_items[i : i + batch_size]
        bytes_list = [item["img_bytes"] for item in chunk]
        captions_list = [item["caption"] or "industrial workpiece" for item in chunk]

        # Embed visual image frames
        img_batch = visual_client.embed_images(bytes_list)
        # Embed semantic captions
        cap_batch = visual_client.embed_texts(captions_list)

        # Spec §6 S8: multimodal fusion of image features + caption semantics
        for item, iv, cv in zip(chunk, img_batch.vectors, cap_batch.vectors, strict=True):
            fused = [0.5 * x + 0.5 * y for x, y in zip(iv, cv)]
            norm = math.hypot(*fused)
            fused_normalized = tuple(x / norm for x in fused)
            embeddings_by_id[item["image_id"]] = fused_normalized

        if (i + batch_size) % 32 == 0 or (i + len(chunk)) == len(extracted_items):
            print(f"  Embedded {min(i + batch_size, len(extracted_items))}/{len(extracted_items)} keyframes on GPU...", flush=True)

    t_embed_end = time.perf_counter()
    print(f"GPU multi-modal embedding complete in {t_embed_end - t_embed_start:.2f}s.", flush=True)

    # 4. Insert into PostgreSQL: images, vec_image, vec_segment_visual
    print("Writing metadata and vectors to PostgreSQL...", flush=True)
    t_db_start = time.perf_counter()

    with session_maker() as session:
        for item in extracted_items:
            img_id = item["image_id"]
            seg_id = item["segment_id"]
            asset_id = item["asset_id"]
            storage_key = item["storage_key"]
            caption = item["caption"]
            vec = embeddings_by_id[img_id]

            # Upsert into images table
            session.execute(
                text(
                    """
                    INSERT INTO images (id, asset_id, segment_id, storage_key, caption, source)
                    VALUES (:id, :asset_id, :segment_id, :storage_key, :caption, 'frame')
                    ON CONFLICT (id) DO UPDATE
                    SET asset_id = EXCLUDED.asset_id,
                        segment_id = EXCLUDED.segment_id,
                        storage_key = EXCLUDED.storage_key,
                        caption = EXCLUDED.caption,
                        source = EXCLUDED.source
                    """
                ),
                {
                    "id": img_id,
                    "asset_id": asset_id,
                    "segment_id": seg_id,
                    "storage_key": storage_key,
                    "caption": caption,
                },
            )

            # Insert into vec_image
            index_image_vector(session, img_id, vec, model=VISUAL_MODEL)

            # Insert into vec_segment_visual
            index_segment_visual_vector(session, seg_id, vec, model=VISUAL_MODEL)

        session.commit()

    t_db_end = time.perf_counter()
    print(f"Database indexing complete in {t_db_end - t_db_start:.2f}s.", flush=True)

    # 5. Verification queries
    with session_maker() as session:
        images_count = session.execute(text("SELECT count(*) FROM images")).scalar()
        vec_image_count = session.execute(text("SELECT count(*) FROM vec_image")).scalar()
        vec_segment_vis_count = session.execute(text("SELECT count(*) FROM vec_segment_visual")).scalar()

    total_elapsed = time.perf_counter() - t_start
    print("=" * 70, flush=True)
    print("  PHASE 3 INGESTION SUMMARY:", flush=True)
    print(f"  - Total Keystep Frames Processed: {len(extracted_items)}", flush=True)
    print(f"  - PostgreSQL images count:         {images_count}", flush=True)
    print(f"  - PostgreSQL vec_image count:      {vec_image_count}", flush=True)
    print(f"  - PostgreSQL vec_segment_visual:   {vec_segment_vis_count}", flush=True)
    print(f"  - Total Elapsed Time:              {total_elapsed:.2f}s ({len(extracted_items)/total_elapsed:.2f} frames/s)", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    main()
