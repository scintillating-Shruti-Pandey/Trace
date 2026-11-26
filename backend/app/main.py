import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

import httpx
import json
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
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
    LLMGroundedAnswerGenerator,
    assemble_evidence,
    validate_citations,
)
from app.ingest.probe import incoming_file
from app.local_models import (
    FasterWhisperTranscriber,
    LocalCandidateReranker,
    LocalModelUnavailable,
    LocalQueryAnalyzer,
    OllamaClient,
    caption_frames,
)
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

    def make_search_service(embedder, visual_client):
        local_client = None
        if settings.query_analysis_enabled or settings.rerank_enabled:
            local_client = OllamaClient(
                settings.llm_endpoint, settings.llm_model, settings.llm_timeout
            )
        return SearchService(
            embedder,
            visual_client=visual_client,
            query_analyzer=(
                LocalQueryAnalyzer(local_client) if settings.query_analysis_enabled else None
            ),
            reranker=(
                LocalCandidateReranker(local_client) if settings.rerank_enabled else None
            ),
            visual_segment_fusion=settings.visual_segment_fusion_enabled,
        )

    @asynccontextmanager
    async def lifespan(app):
        engine = make_engine(settings)
        app.state.sessions = session_factory(engine)
        app.state.engine = engine
        from arq import create_pool
        from arq.connections import RedisSettings
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

    # Serve static assets (logo, background images, etc.) at /static/*
    _static_dir = Path(__file__).parent / "static"
    if _static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(_static_dir)),
                  name="static")

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
                revision = connection.scalar(
                    text("SELECT version_num FROM alembic_version"))
                extensions = set(connection.scalars(
                    text("SELECT extname FROM pg_extension")))
                if revision != "0002" or not {"vector", "pg_trgm"}.issubset(extensions):
                    raise RuntimeError("database schema or extensions missing")

        blob_ok = True
        try:
            await asyncio.to_thread(check_database)
            await app.state.redis.ping()
            if settings.ingest_enabled:
                try:
                    await asyncio.to_thread(BlobStore(settings).ready)
                except Exception:
                    blob_ok = False  # MinIO optional — not a hard readiness failure for demo
        except Exception:
            logger.exception("Readiness check failed")
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return {
            "status": "ready",
            "scope": "corpus_metadata",
            "capabilities": {
                "media_ingest": settings.ingest_enabled,
                "search": settings.search_enabled,
                "blob_store": blob_ok,
            },
        }

    @app.get("/api/v1/status", tags=["corpus"])
    def status(session: Database):
        counts = dict(session.execute(
            select(Asset.kind, func.count()).group_by(Asset.kind)).all())
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
        query = select(RemoteSource).order_by(
            RemoteSource.path, RemoteSource.id)
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
        query = select(Asset).where(
            *filters).order_by(Asset.ingested_at, Asset.id)
        total = session.scalar(
            select(func.count()).select_from(Asset).where(*filters))
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
                    select(Segment).where(Segment.asset_id ==
                                          key).order_by(Segment.start_s)
                )
            ],
            "chunks": [
                row(c)
                for c in session.scalars(
                    select(Chunk).where(
                        Chunk.asset_id == key).order_by(Chunk.idx)
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
        query = select(EvidenceLink).order_by(
            EvidenceLink.created_at, EvidenceLink.id)
        if segment_id:
            query = query.where(EvidenceLink.segment_id == str(segment_id))
        return {"items": [row(link) for link in session.scalars(query.offset(offset).limit(limit))]}

    @app.post("/api/v1/search", tags=["retrieval"])
    def search(
        value: SearchQuery,
        session: Database,
        user: Annotated[AuthUser, Depends(require_role(Role.ENGINEER))] = None,
    ):
        if not settings.search_enabled:
            raise HTTPException(
                503, "Search is disabled until retrieval phase is activated")
        embedder = BgeM3Client(
            api_key=settings.embedding_api_key or settings.deepinfra_api_key,
            endpoint=settings.embedding_endpoint,
        )
        visual_client = SiglipVisualClient(
            endpoint=settings.visual_endpoint,
        )
        service = make_search_service(embedder, visual_client)
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
                exp_segs, exp_chunks = expand_candidates(
                    session, segs, [], query_text=value.query)
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
                exp_segs, exp_chunks = expand_candidates(
                    session, [], chunks, query_text=value.query)
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
            raise HTTPException(
                503, "Search and generation are disabled until retrieval phase is activated")
        embedder = BgeM3Client(
            api_key=settings.embedding_api_key or settings.deepinfra_api_key,
            endpoint=settings.embedding_endpoint,
        )
        visual_client = SiglipVisualClient(
            endpoint=settings.visual_endpoint,
        )
        service = make_search_service(embedder, visual_client)
        multimodal = service.search_multimodal(
            session,
            value.query,
            limit=value.limit,
            equipment_family=value.equipment_family,
            link_expansion=value.link_expansion,
        )
        evidence = assemble_evidence(multimodal, top_k=value.limit)
        generator = LLMGroundedAnswerGenerator(
            ollama_endpoint=settings.llm_endpoint,
            ollama_model=settings.llm_model,
            timeout=settings.llm_timeout,
        ) if settings.llm_enabled else GroundedAnswerGenerator()
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
            llm_used=result.llm_used,
        )

    @app.get("/api/v1/generate/stream", tags=["generation"])
    async def generate_stream(
        query: str = Query(..., min_length=1),
        limit: int = Query(8, ge=1, le=20),
        equipment_family: Family | None = None,
        link_expansion: bool = Query(True),
    ):
        if not settings.search_enabled:
            raise HTTPException(
                503, "Search and generation are disabled until retrieval phase is activated")

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
                    service = make_search_service(embedder, visual_client)
                    multimodal = service.search_multimodal(
                        session,
                        query,
                        limit=limit,
                        equipment_family=equipment_family,
                        link_expansion=link_expansion,
                    )
                    return assemble_evidence(multimodal, top_k=limit)

        evidence = await asyncio.to_thread(retrieve)
        generator = LLMGroundedAnswerGenerator(
            ollama_endpoint=settings.llm_endpoint,
            ollama_model=settings.llm_model,
            timeout=settings.llm_timeout,
        ) if settings.llm_enabled else GroundedAnswerGenerator()

        async def sse_event_stream():
            try:
                async for event in generator.stream_generate(query, evidence):
                    yield f"data: {json.dumps(event)}\n\n"
            except Exception as exc:
                err_payload = json.dumps(
                    {"type": "error", "message": str(exc)})
                yield f"data: {err_payload}\n\n"

        return StreamingResponse(sse_event_stream(), media_type="text/event-stream")

    # ------------------------------------------------------------------ #
    #  IVP — Image & Video Processing on the real IndEgo dataset          #
    # ------------------------------------------------------------------ #
    # Every frame analysed here is decoded from the pinned dataset release
    # through the media proxy below. Nothing is a reconstruction or a
    # placeholder: /api/v1/ivp/frame returns actual dataset pixels.
    @app.get("/api/v1/ivp/catalog", tags=["ivp"])
    def ivp_catalog():
        """Technique syllabus plus the verified dataset inventory."""
        from app.ivp.service import ManifestError, dataset_overview
        from app.ivp.techniques import catalog

        payload = catalog()
        try:
            payload["dataset"] = dataset_overview()
            payload["dataset_available"] = True
        except ManifestError as exc:
            payload["dataset"] = {"error": str(exc)}
            payload["dataset_available"] = False
        return payload

    @app.get("/api/v1/ivp/frame", tags=["ivp"])
    def ivp_frame(
        stem: str = Query(..., min_length=1),
        t: float = Query(0.0, ge=0.0),
        w: int = Query(640, ge=160, le=960),
    ):
        """A real IndEgo frame at time `t`, as PNG, decoded on demand."""
        from app.ivp.frames import FrameError, frame_png
        from app.ivp.manifest import ManifestError

        try:
            payload, meta = frame_png(stem, t, w)
        except ManifestError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FrameError as exc:
            raise HTTPException(503, f"frame unavailable: {exc}") from exc
        return Response(
            content=payload,
            media_type="image/png",
            headers={
                # Dataset-derived pixels must not become persistent browser or proxy cache files.
                "Cache-Control": "no-store",
                "X-Trace-Source": "indego",
                "X-Trace-Timestamp": str(meta["timestamp_s"]),
            },
        )

    @app.post("/api/v1/ivp/analyze", tags=["ivp"])
    async def ivp_analyze(
        request: Request,
        stem: str | None = Query(None),
        t: float = Query(0.0, ge=0.0),
        w: int = Query(640, ge=160, le=960),
    ):
        """Run the full classical IVP pipeline on real footage or a raw upload.

        Send the image as the raw request body (e.g. `Content-Type: image/png`)
        to analyse a captured frame, or omit the body and pass `stem` + `t` to
        analyse a real dataset frame. Built without multipart parsing so the
        runtime needs no extra form-dependency.
        """
        from app.ivp.frames import FrameError
        from app.ivp.manifest import ManifestError
        from app.ivp.service import analyze_dataset_frame, analyze_upload

        try:
            body = await request.body()
            if body:
                label = request.headers.get("x-frame-label", "captured frame")
                return analyze_upload(body, label)
            if not stem:
                raise HTTPException(
                    422, "send an image body, or pass `stem` plus `t` for a dataset frame"
                )
            return analyze_dataset_frame(stem, t, w)
        except ManifestError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FrameError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/v1/ivp/analyze-frame", tags=["ivp"])
    def ivp_analyze_frame(
        stem: str = Query(..., min_length=1),
        t: float = Query(0.0, ge=0.0),
        w: int = Query(640, ge=160, le=960),
    ):
        """Same pipeline as POST /analyze, addressed by dataset coordinates."""
        from app.ivp.frames import FrameError
        from app.ivp.manifest import ManifestError
        from app.ivp.service import analyze_dataset_frame

        try:
            return analyze_dataset_frame(stem, t, w)
        except ManifestError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FrameError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.get("/api/v1/ivp/segment", tags=["ivp"])
    def ivp_segment(
        stem: str = Query(..., min_length=1),
        start: float = Query(..., ge=0.0),
        end: float = Query(..., ge=0.0),
        fps: float = Query(2.0, ge=0.25, le=4.0),
        w: int = Query(640, ge=160, le=960),
    ):
        """Keyframe selection and optical flow across a real time window."""
        from app.ivp.frames import FrameError
        from app.ivp.manifest import ManifestError
        from app.ivp.service import analyze_dataset_range

        if end <= start:
            raise HTTPException(422, "`end` must be greater than `start`")
        try:
            return analyze_dataset_range(stem, start, end, fps=fps, width=w)
        except ManifestError as exc:
            raise HTTPException(404, str(exc)) from exc
        except FrameError as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/api/v1/ivp/enrich", tags=["ivp"])
    def ivp_enrich(
        stem: str = Query(..., min_length=1),
        start: float = Query(..., ge=0.0),
        end: float = Query(..., gt=0.0),
        language: str | None = Query(None, min_length=2, max_length=12),
    ):
        """Caption and transcribe one real dataset interval in memory.

        This optional path is disabled by default. It never stores media or
        enrichment output; ASR timestamps are returned as source-video times.
        """
        if not settings.ivp_ai_enabled:
            raise HTTPException(
                503, "Local captioning/ASR is not activated; model setup needs approval"
            )
        if end <= start or end - start > 60:
            raise HTTPException(422, "`end` must exceed `start` and the interval must be <= 60s")

        from app.ivp.frames import FrameError, FrameRequest, grab_audio_wav, grab_frames
        from app.ivp.manifest import ManifestError, load_manifest
        import cv2

        try:
            entry = load_manifest().get(stem)
            if end > entry.duration_s:
                raise HTTPException(422, "interval extends beyond the source video")
            sample_count = min(8, max(2, int(round((end - start) / 4)) + 1))
            frames = grab_frames(FrameRequest(
                stem=stem, start_s=start, count=sample_count,
                fps=sample_count / (end - start), width=640,
            ))
            encoded_frames = []
            for frame in frames:
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not ok:
                    raise FrameError("could not encode sampled frame for local captioning")
                encoded_frames.append(bytes(encoded))
            audio = grab_audio_wav(stem, start, end - start)
            transcript = FasterWhisperTranscriber(
                settings.asr_model,
                device=settings.asr_device,
                compute_type=settings.asr_compute_type,
            ).transcribe(audio, language=language)
            caption_client = OllamaClient(
                settings.llm_endpoint, settings.ivp_caption_model, settings.llm_timeout
            )
            caption = caption_frames(
                caption_client,
                encoded_frames,
                title=entry.title,
                start_s=start,
                end_s=end,
                transcript=transcript.text,
            )
        except ManifestError as exc:
            raise HTTPException(404, str(exc)) from exc
        except (FrameError, LocalModelUnavailable) as exc:
            raise HTTPException(503, str(exc)) from exc

        return {
            "source": "huggingface:IndEgo",
            "stem": entry.stem,
            "title": entry.title,
            "interval": {"start_s": start, "end_s": end},
            "caption": caption,
            "caption_model": settings.ivp_caption_model,
            "transcript": transcript.text,
            "transcript_model": transcript.model,
            "words": [
                {
                    "text": word.text,
                    "start_s": round(start + word.start_s, 3),
                    "end_s": round(start + word.end_s, 3),
                }
                for word in transcript.words
            ],
            "persisted": False,
        }

    @app.get("/ivp", response_class=HTMLResponse, tags=["demo"])
    def ivp_lab():
        lab_path = Path(__file__).parent / "static" / "ivp_lab.html"
        if not lab_path.exists():
            raise HTTPException(404, "IVP lab page not found")
        return HTMLResponse(content=lab_path.read_text(encoding="utf-8"))

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

    @app.get("/api/v1/media/proxy", tags=["demo"])
    async def media_proxy(url: str = Query(...), request: Request = None):
        """Proxy IndEgo dataset videos for same-origin HTML5 playback with range support."""
        parsed = urlparse(url)
        allowed_prefix = "/datasets/FraunhoferIPK/IndEgo/resolve/"
        if parsed.scheme not in {"https"}:
            raise HTTPException(400, "Only HTTPS media URLs are allowed")
        if parsed.netloc != "huggingface.co" or not parsed.path.startswith(allowed_prefix):
            raise HTTPException(400, "Unsupported media source URL")

        upstream_headers: dict[str, str] = {}
        range_header = request.headers.get("range") if request else None
        if range_header:
            upstream_headers["Range"] = range_header

        client = httpx.AsyncClient(
            follow_redirects=True, timeout=httpx.Timeout(60.0, read=60.0))
        try:
            upstream_request = client.build_request(
                "GET", url, headers=upstream_headers)
            upstream = await client.send(upstream_request, stream=True)
        except httpx.HTTPError as exc:
            await client.aclose()
            raise HTTPException(
                502, f"Media upstream unavailable: {exc}") from exc

        # Some demo labels may point to the wrong IndEgo category directory.
        # If the first URL 404s, retry by swapping 1_Assembly <-> 2_Inspection_Repair.
        if upstream.status_code == 404:
            alt_path = None
            if "/1_Assembly/" in parsed.path:
                alt_path = parsed.path.replace(
                    "/1_Assembly/", "/2_Inspection_Repair/", 1)
            elif "/2_Inspection_Repair/" in parsed.path:
                alt_path = parsed.path.replace(
                    "/2_Inspection_Repair/", "/1_Assembly/", 1)

            if alt_path:
                await upstream.aclose()
                alt_url = parsed._replace(path=alt_path).geturl()
                try:
                    upstream_request = client.build_request(
                        "GET", alt_url, headers=upstream_headers)
                    upstream = await client.send(upstream_request, stream=True)
                except httpx.HTTPError as exc:
                    await client.aclose()
                    raise HTTPException(
                        502, f"Media upstream unavailable: {exc}") from exc

        if upstream.status_code >= 400:
            body = (await upstream.aread()).decode("utf-8", errors="ignore")
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(upstream.status_code,
                                body[:200] or "Media upstream returned error")

        passthrough_headers = {}
        for key in ["content-type", "content-length", "content-range", "accept-ranges", "cache-control"]:
            value = upstream.headers.get(key)
            if value:
                passthrough_headers[key] = value

        async def iter_upstream():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
                await client.aclose()

        return StreamingResponse(
            iter_upstream(),
            status_code=upstream.status_code,
            headers=passthrough_headers,
            media_type=upstream.headers.get("content-type", "video/mp4"),
        )

    return app
