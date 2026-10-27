import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select
from app.config import Settings
from app.db import make_engine, session_factory
from app.models import Asset, Segment


def main():
    settings = Settings()
    engine = make_engine(settings)
    session_maker = session_factory(engine)

    with session_maker() as session:
        stmt = (
            select(Asset)
            .where(Asset.kind == "video")
            .order_by(Asset.title)
        )
        videos = session.execute(stmt).scalars().all()
        print(f"Total video assets: {len(videos)}")
        for v in videos[:5]:
            print(f"ID: {v.id} | Title: {v.title} | Source URI: {v.source_uri}")

        # Count segments
        seg_stmt = (
            select(Segment)
            .where(Segment.method == "manual")
            .order_by(Segment.asset_id, Segment.start_s)
        )
        segs = session.execute(seg_stmt).scalars().all()
        print(f"Total manual keystep segments: {len(segs)}")
        for s in segs[:5]:
            print(f"Seg ID: {s.id} | Video Asset: {s.asset_id} | {s.caption} ({s.start_s:.1f}s - {s.end_s:.1f}s)")


if __name__ == "__main__":
    main()
