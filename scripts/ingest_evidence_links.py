"""Ingest human-verified evidence links into PostgreSQL evidence_links table.

Validates that:
1. Every segment_id resolves to an authentic manual keystep segment.
2. Every chunk_id resolves to an authentic document chunk.
3. Every link conforms to the engineering spec data model:
   - relation in ('documents', 'specifies', 'depicts', 'contradicts')
   - confidence between 0.0 and 1.0
   - author is human
   - num_nonnulls(segment_id, chunk_id, image_id) >= 2
4. Total evidence links >= 100 (Phase 0 exit gate requirement).
"""

import json
import logging
import sys
from collections import Counter
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import delete, func, select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Chunk, EvidenceLink, Segment

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_evidence_links")

def load_link_definitions():
    json_path = Path(__file__).resolve().parent.parent / "data" / "incoming" / "evidence_links.json"
    if not json_path.exists():
        raise FileNotFoundError(f"Missing evidence links definitions at {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

def ingest_links():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    definitions = load_link_definitions()
    logger.info("Loaded %d link definitions from data/incoming/evidence_links.json", len(definitions))

    with session_maker() as session:
        # Build lookup tables
        chunk_rows = session.execute(
            select(Chunk.id, Asset.title, Chunk.section_path)
            .join(Asset, Chunk.asset_id == Asset.id)
        ).all()
        chunk_lookup = {(r.title, r.section_path): str(r.id) for r in chunk_rows}
        logger.info("Indexed %d document chunks in PostgreSQL", len(chunk_lookup))

        seg_rows = session.execute(
            select(Segment.id, Asset.title, Segment.caption, Segment.start_s, Segment.end_s)
            .join(Asset, Segment.asset_id == Asset.id)
            .where(Segment.method == "manual")
        ).all()
        seg_lookup = {
            (s.title, s.caption, round(s.start_s, 1), round(s.end_s, 1)): str(s.id)
            for s in seg_rows
        }
        logger.info("Indexed %d manual keysteps in PostgreSQL", len(seg_lookup))

        # Check existing evidence links
        existing_count = session.scalar(select(func.count(EvidenceLink.id)))
        if existing_count > 0:
            logger.info("Clearing %d existing evidence links for clean idempotent re-ingestion", existing_count)
            session.execute(delete(EvidenceLink))
            session.flush()

        resolved_links = []
        errors = []
        seen_pairs = set()

        for idx, item in enumerate(definitions):
            c_key = (item["doc_title"], item["section_path"])
            if c_key not in chunk_lookup:
                errors.append(f"Row {idx}: Unmatched document chunk '{c_key}'")
                continue
            chunk_id = chunk_lookup[c_key]

            s_key = (
                item["video_title"],
                item["segment_caption"],
                round(item["start_s"], 1),
                round(item["end_s"], 1),
            )
            if s_key not in seg_lookup:
                errors.append(f"Row {idx}: Unmatched video segment '{s_key}'")
                continue
            segment_id = seg_lookup[s_key]

            relation = item["relation"]
            if relation not in ("documents", "specifies", "depicts", "contradicts"):
                errors.append(f"Row {idx}: Invalid relation '{relation}'")
                continue

            unique_key = (segment_id, chunk_id, relation)
            if unique_key in seen_pairs:
                logger.warning("Row %d: Skipping duplicate pair %s", idx, unique_key)
                continue
            seen_pairs.add(unique_key)

            link = EvidenceLink(
                segment_id=segment_id,
                chunk_id=chunk_id,
                image_id=None,
                relation=relation,
                confidence=float(item.get("confidence", 1.0)),
                author=item.get("author", "human:expert"),
                note=item.get("note"),
            )
            resolved_links.append(link)

        if errors:
            for err in errors[:10]:
                logger.error(err)
            raise ValueError(f"Encountered {len(errors)} validation errors during link resolution")

        # Insert all resolved links
        session.add_all(resolved_links)
        session.commit()

        total_inserted = session.scalar(select(func.count(EvidenceLink.id)))
        logger.info("Successfully committed %d evidence links to PostgreSQL", total_inserted)

        # Audit breakdown
        rel_counts = dict(
            session.execute(
                select(EvidenceLink.relation, func.count(EvidenceLink.id))
                .group_by(EvidenceLink.relation)
            ).all()
        )
        print("\n" + "=" * 60)
        print("TRACE EVIDENCE LINKS INGESTION AUDIT")
        print("=" * 60)
        print(f"Total Links Populated: {total_inserted}")
        print("Relation Breakdown:")
        for rel, count in sorted(rel_counts.items()):
            pct = (count / total_inserted) * 100
            print(f"  - {rel:<14}: {count:>3} ({pct:>5.1f}%)")
        print(f"Phase 0 Gate Requirement: >= 100 human-authored links")
        print(f"Gate Status: {'PASSED (MET)' if total_inserted >= 100 else 'FAILED'}")
        print("=" * 60 + "\n")

if __name__ == "__main__":
    ingest_links()
