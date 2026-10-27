import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

import json
from arq import create_pool
from arq.connections import RedisSettings
from arq.jobs import Job
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.corpus import MissingItem, add_chunk, add_link, add_segment, annotate_segment, require, row
from app.db import make_engine, session_factory
from app.embeddings import BgeM3Client
from app.generation import (
    CitationValidationError,
    GroundedAnswerGenerator,
    assemble_evidence,
    validate_citations,
)
from app.ingest.probe import incoming_file
from app.models import Asset, Chunk, EvidenceLink, Image, RemoteSource, Segment, StageStatus
from app.schemas import (
    AssetCreate,
    ChunkCreate,
    CitationItem,
    Family,
    GenerateRequest,
    GenerateResponse,
    Kind,
    LinkCreate,
    SearchQuery,
    SegmentCreate,
    SegmentPatch,
)
from app.auth import AuthUser, Role, require_role
from app.expansion import expand_candidates
from app.search import SearchService
from app.stores.blob import BlobStore
from app.vision import SiglipVisualClient

logger = logging.getLogger(__name__)


def get_session(request: Request):
    with request.app.state.sessions.begin() as session:
        yield session


Database = Annotated[Session, Depends(get_session)]


def create_app(settings: Settings | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(settings)
        app.state.sessions = session_factory(engine)
        app.state.engine = engine
        app.state.redis = await create_pool(RedisSettings.from_dsn(settings.redis_url))
        try:
            yield
        finally:
            await app.state.redis.aclose()
            engine.dispose()

    app = FastAPI(
        title="Trace",
        version="0.1.0",
        description="Phase 0 corpus foundations. Search and model processing are pending.",
        lifespan=lifespan,
    )

    @app.exception_handler(MissingItem)
    async def missing_handler(_, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(ValueError)
    async def validation_handler(_, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def integrity_handler(_, exc):
        return JSONResponse(status_code=409, content={"detail": "Duplicate or conflicting record"})

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        return response

    @app.get("/healthz", tags=["health"])
    def health():
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def ready():
        def check_database():
            with app.state.engine.connect() as connection:
                revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
                extensions = set(connection.scalars(text("SELECT extname FROM pg_extension")))
                if revision != "0002" or not {"vector", "pg_trgm"}.issubset(extensions):
                    raise RuntimeError("database schema or extensions missing")

        try:
            await asyncio.to_thread(check_database)
            await app.state.redis.ping()
            if settings.ingest_enabled:
                await asyncio.to_thread(BlobStore(settings).ready)
        except Exception:
            logger.exception("Readiness check failed")
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {
            "status": "ready",
            "scope": "corpus_metadata",
            "capabilities": {
                "media_ingest": settings.ingest_enabled,
                "search": settings.search_enabled,
            },
        }

    @app.get("/api/v1/status", tags=["corpus"])
    def status(session: Database):
        counts = dict(session.execute(select(Asset.kind, func.count()).group_by(Asset.kind)).all())
        return {
            "phase": "0 — corpus foundations",
            "assets": counts,
            "remote_sources": session.scalar(select(func.count()).select_from(RemoteSource)),
            "segments": session.scalar(select(func.count()).select_from(Segment)),
            "chunks": session.scalar(select(func.count()).select_from(Chunk)),
            "evidence_links": session.scalar(select(func.count()).select_from(EvidenceLink)),
            "phase_0_complete": False,
            "media_ingest_enabled": settings.ingest_enabled,
            "pending": [
                "media storage setup",
                "automated model processing",
                "real linked corpus",
                "human verification",
                "evaluation query authoring",
            ],
        }

    @app.get("/api/v1/remote-sources", tags=["corpus"])
    def remote_sources(
        session: Database,
        offset: int = Query(0, ge=0),
        limit: int = Query(25, ge=1, le=100),
    ):
        query = select(RemoteSource).order_by(RemoteSource.path, RemoteSource.id)
        return {
            "scope": "registered remote references; not processed corpus assets",
            "items": [row(s) for s in session.scalars(query.offset(offset).limit(limit))],
            "total": session.scalar(select(func.count()).select_from(RemoteSource)),
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/assets", tags=["corpus"])
    def assets(
        session: Database,
        kind: Kind | None = None,
        equipment_family: Family | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ):
        filters = []
        if kind:
            filters.append(Asset.kind == kind)
        if equipment_family:
            filters.append(Asset.equipment_family == equipment_family)
        query = select(Asset).where(*filters).order_by(Asset.ingested_at, Asset.id)
        total = session.scalar(select(func.count()).select_from(Asset).where(*filters))
        return {
            "items": [row(a) for a in session.scalars(query.offset(offset).limit(limit))],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @app.get("/api/v1/assets/{asset_id}", tags=["corpus"])
    def asset(asset_id: UUID, session: Database):
        key = str(asset_id)
        return {
            **row(require(session, Asset, key)),
            "segments": [
                row(s)
                for s in session.scalars(
                    select(Segment).where(Segment.asset_id == key).order_by(Segment.start_s)
                )
            ],
            "chunks": [
                row(c)
                for c in session.scalars(
                    select(Chunk).where(Chunk.asset_id == key).order_by(Chunk.idx)
                )
            ],
            "images": [row(i) for i in session.scalars(select(Image).where(Image.asset_id == key))],
            "stages": [
                row(s)
                for s in session.scalars(
                    select(StageStatus)
                    .where(StageStatus.asset_id == key)
                    .order_by(StageStatus.stage)
                )
            ],
        }

    @app.post("/api/v1/assets/{asset_id}/segments", status_code=201, tags=["annotation"])
    def create_segment(asset_id: UUID, value: SegmentCreate, session: Database):
        return add_segment(session, str(asset_id), value)

    @app.get("/api/v1/segments/{segment_id}", tags=["annotation"])
    def segment(segment_id: UUID, session: Database):
        return row(require(session, Segment, str(segment_id)))

    @app.patch("/api/v1/segments/{segment_id}", tags=["annotation"])
    def patch_segment(segment_id: UUID, value: SegmentPatch, session: Database):
        return annotate_segment(session, str(segment_id), value)

    @app.post("/api/v1/assets/{asset_id}/chunks", status_code=201, tags=["annotation"])
    def create_chunk(asset_id: UUID, value: ChunkCreate, session: Database):
        return add_chunk(session, str(asset_id), value)

    @app.get("/api/v1/chunks/{chunk_id}", tags=["annotation"])
    def chunk(chunk_id: UUID, session: Database):
        return row(require(session, Chunk, str(chunk_id)))

    @app.post("/api/v1/links", status_code=201, tags=["annotation"])
    def create_link(value: LinkCreate, session: Database):
        return add_link(session, value)

    @app.get("/api/v1/links", tags=["annotation"])
    def links(
        session: Database,
        segment_id: UUID | None = None,
        offset: int = Query(0, ge=0),
        limit: int = Query(20, ge=1, le=100),
    ):
        query = select(EvidenceLink).order_by(EvidenceLink.created_at, EvidenceLink.id)
        if segment_id:
            query = query.where(EvidenceLink.segment_id == str(segment_id))
        return {"items": [row(link) for link in session.scalars(query.offset(offset).limit(limit))]}

    @app.post("/api/v1/ingest", status_code=202, tags=["ingestion"])
    async def ingest(
        value: AssetCreate,
        _user: Annotated[AuthUser, Depends(require_role(Role.ADMIN))] = None,
    ):
        if not settings.ingest_enabled:
            raise HTTPException(503, "Media ingestion is disabled until MinIO setup is completed")
        incoming_file(settings.incoming_dir, value.path)
        job = await app.state.redis.enqueue_job("ingest_asset", value.model_dump())
        return {"job_id": job.job_id, "scope": "registration_only"}

    @app.get("/api/v1/ingest/{job_id}", tags=["ingestion"])
    async def ingest_status(job_id: UUID):
        job = Job(job_id.hex, app.state.redis)
        status_value = await job.status()
        if status_value.value == "not_found":
            raise HTTPException(404, "Job not found or result expired (seven-day retention)")
        info = await job.result_info()
        result = info.result if info and info.success else None
        return {"job_id": job_id.hex, "status": status_value.value, "result": result}

    @app.post("/api/v1/search", tags=["retrieval"])
    def search(
        value: SearchQuery,
        session: Database,
        _user: Annotated[AuthUser, Depends(require_role(Role.ENGINEER))] = None,
    ):
        if not settings.search_enabled:
            raise HTTPException(503, "Search is disabled until retrieval phase is activated")
        embedder = BgeM3Client(
            api_key=settings.embedding_api_key or settings.deepinfra_api_key,
            endpoint=settings.embedding_endpoint,
        )
        visual_client = SiglipVisualClient(
            endpoint=settings.visual_endpoint,
        )
        service = SearchService(embedder, visual_client=visual_client)
        if value.modality == "all":
            return service.search_multimodal(
                session,
                value.query,
                limit=value.limit,
                equipment_family=value.equipment_family,
                link_expansion=value.link_expansion,
            )
        output: dict[str, object] = {
            "query": value.query,
            "modality": value.modality,
            "link_expansion_enabled": value.link_expansion,
        }
        if value.modality == "video":
            segs = service.search_video_segments(
                session,
                value.query,
                limit=value.limit,
                equipment_family=value.equipment_family,
            )
            for s in segs:
                s.setdefault("lanes", ["segment_dense"])
            if value.link_expansion:
                exp_segs, exp_chunks = expand_candidates(session, segs, [], query_text=value.query)
                output["video_segments"] = exp_segs[:value.limit]
                if exp_chunks:
                    output["linked_documents"] = exp_chunks
            else:
                output["video_segments"] = segs
        elif value.modality == "document":
            chunks = service.search_documents_hybrid(
                session,
                value.query,
                limit=value.limit,
            )
            for c in chunks:
                c.setdefault("lanes", ["chunk_hybrid_rrf"])
            if value.link_expansion:
                exp_segs, exp_chunks = expand_candidates(session, [], chunks, query_text=value.query)
                output["document_chunks"] = exp_chunks[:value.limit]
                if exp_segs:
                    output["linked_videos"] = exp_segs
            else:
                output["document_chunks"] = chunks
        elif value.modality == "image":
            imgs = service.search_images(
                session,
                value.query,
                limit=value.limit,
            )
            for img in imgs:
                img.setdefault("lanes", ["image_visual"])
            output["images"] = imgs
        return output

    @app.post("/api/v1/generate", response_model=GenerateResponse, tags=["generation"])
    def generate_answer(value: GenerateRequest, session: Database):
        if not settings.search_enabled:
            raise HTTPException(503, "Search and generation are disabled until retrieval phase is activated")
        embedder = BgeM3Client(
            api_key=settings.embedding_api_key or settings.deepinfra_api_key,
            endpoint=settings.embedding_endpoint,
        )
        visual_client = SiglipVisualClient(
            endpoint=settings.visual_endpoint,
        )
        service = SearchService(embedder, visual_client=visual_client)
        multimodal = service.search_multimodal(
            session,
            value.query,
            limit=value.limit,
            equipment_family=value.equipment_family,
            link_expansion=value.link_expansion,
        )
        evidence = assemble_evidence(multimodal, top_k=value.limit)
        generator = GroundedAnswerGenerator()
        try:
            result = generator.generate(value.query, evidence)
        except CitationValidationError as e:
            raise HTTPException(500, detail=str(e))

        citation_items = [
            CitationItem(
                citation_id=e.citation_id,
                kind=e.kind,
                source_id=e.source_id,
                asset_id=e.asset_id,
                title=e.title,
                locator=e.locator,
                text_snippet=e.text[:140],
                score=e.score,
                seek_to_s=e.seek_to_s,
            )
            for e in result.citations
        ]
        return GenerateResponse(
            query=result.query,
            answer=result.answer,
            abstained=result.abstained,
            abstention_reason=result.abstention_reason,
            citations=citation_items,
            evidence_count=result.evidence_count,
        )

    @app.get("/api/v1/generate/stream", tags=["generation"])
    async def generate_stream(
        query: str = Query(..., min_length=1),
        limit: int = Query(8, ge=1, le=20),
        equipment_family: Family | None = None,
        link_expansion: bool = Query(True),
    ):
        if not settings.search_enabled:
            raise HTTPException(503, "Search and generation are disabled until retrieval phase is activated")

        def retrieve():
            with app.state.engine.connect() as conn:
                with Session(bind=conn) as session:
                    embedder = BgeM3Client(
                        api_key=settings.embedding_api_key or settings.deepinfra_api_key,
                        endpoint=settings.embedding_endpoint,
                    )
                    visual_client = SiglipVisualClient(
                        endpoint=settings.visual_endpoint,
                    )
                    service = SearchService(embedder, visual_client=visual_client)
                    multimodal = service.search_multimodal(
                        session,
                        query,
                        limit=limit,
                        equipment_family=equipment_family,
                        link_expansion=link_expansion,
                    )
                    return assemble_evidence(multimodal, top_k=limit)

        evidence = await asyncio.to_thread(retrieve)
        generator = GroundedAnswerGenerator()

        async def sse_event_stream():
            try:
                async for event in generator.stream_generate(query, evidence):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                err_payload = json.dumps({"type": "error", "message": str(exc)})
                yield f"data: {err_payload}\n\n"

        return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

    @app.get("/", response_class=HTMLResponse, tags=["demo"])
    def root():
        demo_path = Path(__file__).parent / "static" / "seek_demo.html"
        if not demo_path.exists():
            raise HTTPException(404, "Seek demo template not found")
        return HTMLResponse(content=demo_path.read_text(encoding="utf-8"))

    @app.get("/demo/seek", response_class=HTMLResponse, tags=["demo"])
    def seek_demo():
        return root()

    @app.get("/corpus", response_class=HTMLResponse, tags=["demo"])
    def corpus_view():
        return root()

    @app.get("/eval", response_class=HTMLResponse, tags=["demo"])
    def eval_view():
        return root()

    @app.get("/trace_logo.png", tags=["demo"])
    def get_logo():
        logo_path = Path(__file__).parent / "static" / "trace_logo.png"
        if not logo_path.exists():
            raise HTTPException(404, "Logo not found")
        return FileResponse(logo_path, media_type="image/png")

    @app.get("/static/trace_logo.png", tags=["demo"])
    def get_static_logo():
        return get_logo()

    @app.get("/bg-clouds.jpg", tags=["demo"])
    def get_bg_clouds():
        bg_path = Path(__file__).parent / "static" / "bg-clouds.jpg"
        if not bg_path.exists():
            raise HTTPException(404, "Background image not found")
        return FileResponse(bg_path, media_type="image/jpeg")

    @app.get("/static/bg-clouds.jpg", tags=["demo"])
    def get_static_bg_clouds():
        return get_bg_clouds()

    return app
