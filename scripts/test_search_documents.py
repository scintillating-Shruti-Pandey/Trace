"""Test Document Hybrid Search against Ingested Corpus."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings
from app.db import make_engine, session_factory
from app.embeddings import BgeM3Client
from app.search import SearchService, search_chunks_dense, search_chunks_lexical

TEST_QUERIES = [
    "torque specification for tabletop mounting bolts",
    "axial clearance feeler gauge lower hinge",
    "hydraulic pump compensator relief valve 180 bar",
    "emergency stop safety relay SMR-CAT4",
    "P/N CMP-402 camera plate mounting screws",
]


def test_document_search():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    client = BgeM3Client(endpoint="http://127.0.0.1:8001/v1/embeddings")
    svc = SearchService(client)

    print("=" * 70)
    print("  LIVE DOCUMENT HYBRID SEARCH VERIFICATION")
    print("=" * 70)

    with session_maker() as session:
        for q in TEST_QUERIES:
            print(f"\nQUERY: \"{q}\"")

            # Dense only
            emb = client.embed([q]).vectors[0]
            dense_hits = search_chunks_dense(session, emb, limit=1)
            d_hit = dense_hits[0] if dense_hits else None
            if d_hit:
                print(f"  [DENSE #1]  (score {d_hit['score']:.4f}) {d_hit['section_path']}")

            # Lexical only
            lex_hits = search_chunks_lexical(session, q, limit=1)
            l_hit = lex_hits[0] if lex_hits else None
            if l_hit:
                print(f"  [BM25 #1]   (score {l_hit['score']:.4f}) {l_hit['section_path']}")

            # Hybrid RRF
            hybrid_hits = svc.search_documents_hybrid(session, q, limit=3)
            h_hit = hybrid_hits[0] if hybrid_hits else None
            if h_hit:
                print(f"  [HYBRID #1] (RRF {h_hit['score']:.4f}) {h_hit['asset_title']}")
                print(f"              {h_hit['section_path']}")
                print(f"              Snippet: {h_hit['text'][:120]}...")


if __name__ == "__main__":
    test_document_search()
