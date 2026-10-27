import json
import sys
from pathlib import Path

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
            select(EvidenceLink, Segment, Chunk, Asset)
            .join(Segment, EvidenceLink.segment_id == Segment.id)
            .join(Chunk, EvidenceLink.chunk_id == Chunk.id)
            .join(Asset, Chunk.asset_id == Asset.id)
            .order_by(EvidenceLink.relation, Segment.caption)
        )
        results = session.execute(stmt).all()
        print(f"Loaded {len(results)} candidate links for query construction.")

        # Let's inspect some of each relation
        for rel in ["contradicts", "depicts", "specifies", "documents"]:
            subset = [r for r in results if r[0].relation == rel]
            print(f"\n=== Relation: {rel} ({len(subset)} links) ===")
            for i, (link, seg, chunk, asset) in enumerate(subset[:3]):
                print(f"[{i+1}] Seg: '{seg.caption}' ({seg.start_s:.1f}s-{seg.end_s:.1f}s)")
                print(f"    Doc: '{asset.title}' § {chunk.section_path}")
                print(f"    Note: {link.note[:120]}...")


if __name__ == "__main__":
    main()
