import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import Settings
from app.ingest.probe import incoming_file, probe_video
from app.models import Asset, Chunk, EvidenceLink, Image, Segment, StageStatus, uid
from app.schemas import AssetCreate, ChunkCreate, LinkCreate, SegmentCreate, SegmentPatch


class MissingItem(ValueError):
    pass


def require(session: Session, model, item_id: str):
    obj = session.get(model, item_id)
    if obj is None:
        raise MissingItem(f"{model.__name__} not found")
    return obj


def row(obj):
    return {column.key: getattr(obj, column.key) for column in obj.__mapper__.column_attrs}


def register(session: Session, manifest: AssetCreate, settings: Settings, blobs):
    source = incoming_file(settings.incoming_dir, manifest.path)
    # Hash the same immutable snapshot that gets probed and uploaded.
    with TemporaryDirectory(prefix="trace-register-") as folder:
        snapshot = Path(folder) / source.name
        digest = hashlib.sha256()
        with source.open("rb") as inp, snapshot.open("wb") as out:
            while block := inp.read(1024 * 1024):
                digest.update(block)
                out.write(block)
        checksum = digest.hexdigest()
        # Serialize corpus additions across workers to enforce checksum dedupe and scope caps.
        session.execute(text("SELECT pg_advisory_xact_lock(8742201)"))
        existing = session.scalar(select(Asset).where(Asset.checksum_sha256 == checksum))
        if existing:
            if existing.kind != manifest.kind:
                raise ValueError("this file is already registered with a different asset kind")
            return {"asset_id": existing.id, "deduplicated": True, "status": "registered"}
        count = session.scalar(
            select(func.count()).select_from(Asset).where(Asset.kind == manifest.kind)
        )
        cap = {"video": 25, "image": 500, "document": 90}[manifest.kind]
        if count >= cap:
            raise ValueError(f"corpus cap reached for {manifest.kind}: {cap}")
        metadata = probe_video(snapshot, settings.ffprobe_bin) if manifest.kind == "video" else {}
        if manifest.kind == "video":
            total = session.scalar(select(func.coalesce(func.sum(Asset.duration_s), 0)))
            if total + metadata["duration_s"] > 6 * 3600:
                raise ValueError("corpus duration would exceed the six-hour hard cap")
        asset_id = uid()
        key = f"originals/{asset_id}/{source.name}"
        blobs.put_file(snapshot, key)
        asset = Asset(
            id=asset_id,
            storage_key=key,
            checksum_sha256=checksum,
            duration_s=metadata.get("duration_s"),
            meta=metadata.get("probe", {}),
            **manifest.model_dump(exclude={"path"}),
        )
        session.add(asset)
        session.flush()
        session.add(
            StageStatus(
                asset_id=asset_id,
                stage="S0" if manifest.kind == "video" else "register",
                status="done",
                input_hash=checksum,
            )
        )
        if manifest.kind == "image":
            session.add(Image(asset_id=asset_id, storage_key=key, source="standalone"))
        session.flush()
        return {"asset_id": asset_id, "deduplicated": False, "status": "registered"}


def add_segment(session: Session, asset_id: str, value: SegmentCreate):
    asset = require(session, Asset, asset_id)
    # Lock parent so concurrent annotation requests cannot create overlaps or duplicate indices.
    session.execute(select(Asset.id).where(Asset.id == asset_id).with_for_update())
    if asset.kind != "video":
        raise ValueError("segments require a video asset")
    if asset.duration_s is None or value.end_s > asset.duration_s:
        raise ValueError("segment extends beyond the video duration")
    segments = list(session.scalars(select(Segment).where(Segment.asset_id == asset_id)))
    if any(
        s.method != "fixed-30s" and s.start_s < value.end_s and s.end_s > value.start_s
        for s in segments
    ):
        raise ValueError("segment overlaps an existing shot or manual segment")
    segment = Segment(
        asset_id=asset_id,
        idx=max((s.idx for s in segments), default=-1) + 1,
        method="manual",
        annotation_author=value.author,
        **value.model_dump(exclude={"author"}),
    )
    session.add(segment)
    session.flush()
    return row(segment)


def annotate_segment(session: Session, segment_id: str, value: SegmentPatch):
    segment = require(session, Segment, segment_id)
    segment.human_caption = value.human_caption
    segment.human_verified = value.human_verified
    segment.annotation_author = value.author
    session.flush()
    return row(segment)


def add_chunk(session: Session, asset_id: str, value: ChunkCreate):
    asset = require(session, Asset, asset_id)
    session.execute(select(Asset.id).where(Asset.id == asset_id).with_for_update())
    if asset.kind != "document":
        raise ValueError("chunks require a document asset")
    idx = session.scalar(select(func.max(Chunk.idx)).where(Chunk.asset_id == asset_id))
    chunk = Chunk(asset_id=asset_id, idx=0 if idx is None else idx + 1, **value.model_dump())
    session.add(chunk)
    session.flush()
    return row(chunk)


def add_link(session: Session, value: LinkCreate):
    data = value.model_dump(mode="json")
    for field, model in (("segment_id", Segment), ("chunk_id", Chunk), ("image_id", Image)):
        if data[field]:
            require(session, model, data[field])
    link = EvidenceLink(**data)
    session.add(link)
    session.flush()
    return row(link)
