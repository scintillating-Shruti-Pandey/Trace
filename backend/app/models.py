from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def uid():
    return str(uuid4())


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class RemoteSource(Base):
    """Remote provenance only: not an ingested asset, caption, or ground-truth record."""

    __tablename__ = "remote_sources"
    __table_args__ = (UniqueConstraint("repo", "revision", "path"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True)
    repo: Mapped[str] = mapped_column(Text)
    revision: Mapped[str] = mapped_column(Text)
    path: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text)
    duration_s: Mapped[float] = mapped_column(Float)
    trial_group: Mapped[str] = mapped_column(Text)
    verification: Mapped[dict] = mapped_column(JSON)
    registered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (CheckConstraint("kind IN ('video','image','document')"),)
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(Text)
    source_uri: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str] = mapped_column(Text)
    license: Mapped[str] = mapped_column(Text)
    redistributable: Mapped[bool] = mapped_column(Boolean, default=False)
    equipment_family: Mapped[str] = mapped_column(String(30))
    duration_s: Mapped[float | None] = mapped_column(Float)
    checksum_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    meta: Mapped[dict] = mapped_column(JSON, default=dict)


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        UniqueConstraint("asset_id", "method", "idx"),
        CheckConstraint("start_s >= 0 AND end_s > start_s"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE")
    )
    idx: Mapped[int] = mapped_column(Integer)
    start_s: Mapped[float] = mapped_column(Float)
    end_s: Mapped[float] = mapped_column(Float)
    method: Mapped[str] = mapped_column(String(30), default="manual")
    caption: Mapped[str | None] = mapped_column(Text)
    human_caption: Mapped[str | None] = mapped_column(Text)
    human_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    annotation_author: Mapped[str | None] = mapped_column(Text)
    transcript: Mapped[str | None] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("asset_id", "idx"),
        CheckConstraint("doc_type IN ('manual','sop','report')"),
        CheckConstraint("token_count > 0"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    asset_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE")
    )
    idx: Mapped[int] = mapped_column(Integer)
    doc_type: Mapped[str] = mapped_column(String(20))
    section_path: Mapped[str] = mapped_column(Text)
    page_from: Mapped[int | None] = mapped_column(Integer)
    page_to: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    token_count: Mapped[int] = mapped_column(Integer)


class Image(Base):
    __tablename__ = "images"
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    asset_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE")
    )
    segment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("segments.id", ondelete="SET NULL")
    )
    storage_key: Mapped[str] = mapped_column(Text)
    caption: Mapped[str | None] = mapped_column(Text)
    ocr_text: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20))


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint(
            "segment_id", "chunk_id", "image_id", "relation", postgresql_nulls_not_distinct=True
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1"),
    )
    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=uid)
    segment_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("segments.id", ondelete="CASCADE")
    )
    chunk_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("chunks.id", ondelete="CASCADE")
    )
    image_id: Mapped[str | None] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("images.id", ondelete="CASCADE")
    )
    relation: Mapped[str] = mapped_column(String(30))
    confidence: Mapped[float] = mapped_column(Float, default=1)
    author: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class StageStatus(Base):
    __tablename__ = "stage_status"
    __table_args__ = (CheckConstraint("status IN ('pending','running','done','failed')"),)
    asset_id: Mapped[str] = mapped_column(
        Uuid(as_uuid=False), ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(30), primary_key=True)
    status: Mapped[str] = mapped_column(String(20))
    input_hash: Mapped[str] = mapped_column(String(64))
    error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
