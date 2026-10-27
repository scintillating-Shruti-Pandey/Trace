import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Chunk, EvidenceLink, Segment

def main():
    settings = Settings()
    engine = make_engine(settings)
    Session = session_factory(engine)
    
    with Session() as session:
        stmt = (
            select(
                EvidenceLink,
                Segment,
                Chunk,
            )
            .join(Segment, EvidenceLink.segment_id == Segment.id)
            .join(Chunk, EvidenceLink.chunk_id == Chunk.id)
            .order_by(EvidenceLink.relation, Segment.caption)
        )
        results = session.execute(stmt).all()
        print(f"Total evidence links fetched: {len(results)}")
        
        relations = {}
        for link, seg, chunk in results:
            relations[link.relation] = relations.get(link.relation, 0) + 1
        print(f"Relation counts: {relations}")
        
        # Print sample from each relation
        seen_rel = set()
        for link, seg, chunk in results:
            if link.relation not in seen_rel:
                seen_rel.add(link.relation)
                print(f"\n--- Sample for relation: {link.relation} ---")
                print(f"Segment: {seg.caption} [{seg.start_s:.1f}s - {seg.end_s:.1f}s]")
                print(f"Chunk: § {chunk.section_path} ({chunk.heading})")
                print(f"Note: {link.note}")
                print(f"IDs: link={link.id}, seg={seg.id}, chunk={chunk.id}, vid_asset={seg.asset_id}, doc_asset={chunk.asset_id}")

if __name__ == "__main__":
    main()
