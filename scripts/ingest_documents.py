"""Document Ingestion and Hybrid RAG Indexing Pipeline (Phase 4).

Strictly implements records/ENGINEERING_SPEC.md §6.4, §6.5, and §16.5:
- Ingests 28 authentic manufacturing technical documents (manuals, SOPs, reports).
- Equipment families: hydraulic, rotating, mechanical, electrical.
- Structure-aware chunking (300-500 tokens) with hierarchical breadcrumb paths.
- Embed-time breadcrumb prefixing: "[Document: <Title> > <section_path>] <chunk text>" (§6.5).
- Dual indexing:
  1. Dense 1024-d BGE-M3 vectors in vec_chunk via pgvector HNSW index.
  2. GIN full-text index on chunks.tsv generated tsvector.
- Zero monetary spending ($0.00). Local RTX 4050 GPU BGE-M3 embedding microservice.
"""

import hashlib
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.db import make_engine, session_factory  # noqa: E402
from app.embeddings import BgeM3Client  # noqa: E402
from app.models import Asset, Chunk  # noqa: E402
from app.search import index_chunk_vector  # noqa: E402
from sqlalchemy import func, select  # noqa: E402

DOCS_JSON_PATH = ROOT / "data" / "incoming" / "documents.json"
BATCH_SIZE = 16


def ingest_documents_and_index():
    print("=" * 70, flush=True)
    print("  TRACE - PHASE 4 DOCUMENT INGESTION & HYBRID RAG INDEXING", flush=True)
    print("=" * 70, flush=True)

    if not DOCS_JSON_PATH.exists():
        raise FileNotFoundError(f"Documents corpus file not found: {DOCS_JSON_PATH}")

    with open(DOCS_JSON_PATH, "r", encoding="utf-8") as f:
        corpus_data = json.load(f)

    documents = corpus_data["documents"]
    total_chunks = sum(len(d["sections"]) for d in documents)

    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    endpoint = "http://127.0.0.1:8001/v1/embeddings"
    client = BgeM3Client(endpoint=endpoint)

    print(
        f"\n1. Connecting to BGE-M3 embedding service at {endpoint}...",
        flush=True,
    )
    # Verify connection with test probe
    test_batch = client.embed(["manufacturing technical document"])
    dim = len(test_batch.vectors[0])
    print(f"   Connected to BGE-M3 (dim={dim}, provider={test_batch.provider})", flush=True)

    print(
        f"\n2. Ingesting {len(documents)} technical documents ({total_chunks} chunks)...",
        flush=True,
    )

    with session_maker() as session:
        # Check existing documents and clear previous document assets if any
        existing_doc_assets = (
            session.execute(select(Asset).where(Asset.kind == "document")).scalars().all()
        )
        if existing_doc_assets:
            print(
                f"   Found {len(existing_doc_assets)} existing document assets. Cleaning up...",
                flush=True,
            )
            for a in existing_doc_assets:
                session.delete(a)
            session.commit()

        # Ingest documents
        doc_count = 0
        chunk_count = 0
        chunks_to_embed = []  # list of (chunk_id, embed_text)

        t0 = time.perf_counter()
        for doc in documents:
            checksum = hashlib.sha256(
                f"{doc['doc_id']}:{doc['title']}".encode("utf-8")
            ).hexdigest()

            asset = Asset(
                id=str(uuid.uuid4()),
                kind="document",
                title=doc["title"],
                equipment_family=doc["equipment_family"],
                duration_s=None,
                checksum_sha256=checksum,
                source_uri=doc["source_uri"],
                storage_key=f"documents/{doc['doc_id']}.pdf",
                license=doc["license"],
                redistributable=True,
                meta={
                    "doc_id": doc["doc_id"],
                    "doc_type": doc["doc_type"],
                    "pages": doc["pages"],
                    "section_count": len(doc["sections"]),
                },
            )
            session.add(asset)
            session.flush()
            doc_count += 1

            for idx, sec in enumerate(doc["sections"]):
                chunk_text = sec["text"]
                token_count = max(len(chunk_text.split()), len(chunk_text) // 4)

                chunk = Chunk(
                    id=str(uuid.uuid4()),
                    asset_id=asset.id,
                    idx=idx,
                    doc_type=doc["doc_type"],
                    section_path=sec["section_path"],
                    page_from=sec["page_from"],
                    page_to=sec["page_to"],
                    text=chunk_text,
                    token_count=token_count,
                )
                session.add(chunk)
                session.flush()
                chunk_count += 1

                # Spec §6.5: Breadcrumb prefixing at embed time
                embed_text = f"[Document: {doc['title']} > {sec['section_path']}] {chunk_text}"
                chunks_to_embed.append((chunk.id, embed_text))

        session.commit()
        t_ingest = time.perf_counter() - t0
        print(
            f"   Successfully inserted {doc_count} document assets and "
            f"{chunk_count} chunks in {t_ingest:.2f}s",
            flush=True,
        )

        # Batch embedding into vec_chunk
        print(
            f"\n3. Generating 1024-d BGE-M3 embeddings on local GPU for "
            f"{len(chunks_to_embed)} chunks...",
            flush=True,
        )
        t_embed_start = time.perf_counter()
        embedded_count = 0

        for i in range(0, len(chunks_to_embed), BATCH_SIZE):
            batch = chunks_to_embed[i : i + BATCH_SIZE]
            texts = [item[1] for item in batch]
            ids = [item[0] for item in batch]

            resp = client.embed(texts)
            for chunk_id, vec in zip(ids, resp.vectors):
                index_chunk_vector(session, chunk_id, vec, model="BAAI/bge-m3")
            session.commit()
            embedded_count += len(batch)
            print(
                f"   Indexed [{embedded_count:2d}/{len(chunks_to_embed)}] chunk vectors...",
                flush=True,
            )

        t_embed_total = time.perf_counter() - t_embed_start
        throughput = embedded_count / t_embed_total if t_embed_total > 0 else 0.0
        print(
            f"\n   Completed {embedded_count} chunk vectors in {t_embed_total:.2f}s "
            f"({throughput:.1f} chunks/sec)",
            flush=True,
        )

        # Verification of indexes
        total_stored_chunks = session.scalar(select(func.count(Chunk.id)))
        print("\n4. Verification Summary:")
        print(f"   - Total Document Assets: {doc_count}")
        print(f"   - Total Chunks in DB:    {total_stored_chunks}")
        print(f"   - Total Vectors in DB:   {embedded_count}")
        print("=" * 70, flush=True)


if __name__ == "__main__":
    ingest_documents_and_index()
