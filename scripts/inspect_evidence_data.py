import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import func, select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Chunk, EvidenceLink, Segment

def main():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)
    
    with session_maker() as session:
        n_assets = session.scalar(select(func.count(Asset.id)))
        n_videos = session.scalar(select(func.count(Asset.id)).where(Asset.kind == "video"))
        n_docs = session.scalar(select(func.count(Asset.id)).where(Asset.kind == "document"))
        n_manual_segs = session.scalar(select(func.count(Segment.id)).where(Segment.method == "manual"))
        n_fixed_segs = session.scalar(select(func.count(Segment.id)).where(Segment.method == "fixed-30s"))
        n_chunks = session.scalar(select(func.count(Chunk.id)))
        n_links = session.scalar(select(func.count(EvidenceLink.id)))
        
        print(f"Total Assets: {n_assets} (Videos: {n_videos}, Documents: {n_docs})")
        print(f"Segments: {n_manual_segs} manual keysteps, {n_fixed_segs} fixed-30s windows")
        print(f"Chunks: {n_chunks} document chunks")
        print(f"Existing Evidence Links: {n_links}")
        
        # Sample some manual segments
        manual_segs = session.execute(
            select(Segment.id, Segment.asset_id, Segment.caption, Segment.start_s, Segment.end_s, Asset.title)
            .join(Asset, Segment.asset_id == Asset.id)
            .where(Segment.method == "manual")
            .limit(10)
        ).all()
        print("\nSample Manual Keysteps:")
        for seg in manual_segs:
            print(f" - [{seg.title}] ({seg.start_s:.1f}s - {seg.end_s:.1f}s): {seg.caption[:80]}...")

        # Sample some chunks
        chunks = session.execute(
            select(Chunk.id, Chunk.asset_id, Chunk.doc_type, Chunk.section_path, Chunk.text, Asset.title)
            .join(Asset, Chunk.asset_id == Asset.id)
            .limit(10)
        ).all()
        print("\nSample Chunks:")
        for ch in chunks:
            print(f" - [{ch.title} > {ch.section_path}] ({ch.doc_type}): {ch.text[:80]}...")

if __name__ == "__main__":
    main()
