"""Interactive and batch retrieval verification against the indexed IndEgo corpus.

Demonstrates dense pgvector retrieval with BGE-M3 on real industrial video segments.
"""

import sys
import time
from pathlib import Path

# Ensure backend modules can be imported
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from app.embeddings import BgeM3Client
from app.search import SearchService

TEST_QUERIES = [
    "dismount cover and loosen screws",
    "inspect roller bearings for damage",
    "attach wiring harness connector",
    "assemble hydraulic pump valve",
    "remove safety casing with screwdriver",
]


def run_retrieval_verification():
    print("=" * 70, flush=True)
    print("  TRACE — RETRIEVAL VERIFICATION ON INDEXED INDEGO CORPUS", flush=True)
    print("=" * 70, flush=True)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    client = BgeM3Client(endpoint=settings.embedding_endpoint)
    searcher = SearchService(client)

    with session_maker() as session:
        for q_idx, query in enumerate(TEST_QUERIES, start=1):
            t0 = time.perf_counter()
            results = searcher.search_video_segments(session, query, limit=3)
            latency_ms = (time.perf_counter() - t0) * 1000

            print(
                f'\nQuery [{q_idx}/{len(TEST_QUERIES)}]: "{query}" (latency: {latency_ms:.1f}ms)',
                flush=True,
            )
            if not results:
                print("  No matching segments found.", flush=True)
                continue

            for rank, r in enumerate(results, start=1):
                title = r.get("asset_title", "Unknown")
                start = r.get("start_s", 0.0)
                end = r.get("end_s", 0.0)
                score = r.get("score", 0.0)
                caption = r.get("caption", "").strip()
                print(
                    f"  Rank #{rank} [similarity: {score:.4f}] | {title} | "
                    f"{start:.1f}s - {end:.1f}s",
                    flush=True,
                )
                print(f"    Text: {caption}", flush=True)

    print("\n" + "=" * 70, flush=True)
    print("  VERIFICATION COMPLETE — ALL QUERIES EXECUTED SUCCESSFULLY", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    run_retrieval_verification()
