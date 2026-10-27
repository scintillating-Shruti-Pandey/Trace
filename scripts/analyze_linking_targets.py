import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from collections import Counter
from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Segment, Chunk

def main():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    
    with session_maker() as session:
        segs = session.execute(
            select(Segment.id, Segment.asset_id, Segment.caption, Segment.start_s, Segment.end_s, Asset.title)
            .join(Asset, Segment.asset_id == Asset.id)
            .where(Segment.method == "manual")
        ).all()
        
        captions = [s.caption for s in segs]
        print(f"Total manual keysteps: {len(segs)}")
        counts = Counter(captions)
        print("\nKeystep action distribution:")
        for cap, c in counts.most_common():
            print(f"  {cap}: {c}")
            
        print("\nAll 28 documents with their chunks:")
        chunks = session.execute(
            select(Chunk.id, Chunk.asset_id, Chunk.doc_type, Chunk.section_path, Asset.title)
            .join(Asset, Chunk.asset_id == Asset.id)
            .order_by(Asset.title, Chunk.idx)
        ).all()
        
        doc_map = {}
        for ch in chunks:
            doc_map.setdefault(ch.title, []).append((ch.id, ch.doc_type, ch.section_path))
            
        for doc_title, ch_list in doc_map.items():
            print(f"\nDocument: {doc_title} ({len(ch_list)} chunks)")
            for ch_id, dtype, path in ch_list:
                print(f"   [{dtype}] {path} (ID: {ch_id})")

if __name__ == "__main__":
    main()
