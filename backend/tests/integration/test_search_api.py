import json
import os

import pytest
from app.config import Settings
from app.db import make_engine
from app.embeddings import DIMENSIONS, EmbeddingBatch
from app.generation import validate_citations
from app.main import create_app, get_session
from app.vision import DIMENSIONS as VISUAL_DIMENSIONS, VisualEmbeddingBatch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

pytestmark = pytest.mark.skipif(
    os.environ.get("TRACE_INTEGRATION") != "1",
    reason="set TRACE_INTEGRATION=1 with Compose running",
)


@pytest.fixture
def database():
    engine = make_engine(Settings())
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            yield session
        transaction.rollback()
    engine.dispose()


@pytest.fixture
def client(database):
    app = create_app(Settings(ingest_enabled=False, search_enabled=True))

    def override():
        yield database

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client


def test_search_disabled_by_default(database):
    app = create_app(Settings(ingest_enabled=False, search_enabled=False))

    def override():
        yield database

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        ready = test_client.get("/readyz")
        assert ready.json()["capabilities"]["search"] is False
        res = test_client.post("/api/v1/search", json={"query": "test"})
        assert res.status_code == 503
        assert "disabled" in res.json()["detail"]


def test_readyz_reports_search_capability_when_enabled(client):
    res = client.get("/readyz")
    assert res.status_code == 200
    assert res.json()["capabilities"]["search"] is True


def test_search_endpoint_validates_input(client):
    res = client.post("/api/v1/search", json={"query": "", "modality": "all"})
    assert res.status_code == 422


def test_search_endpoint_executes(client, monkeypatch):
    mock_batch = EmbeddingBatch(
        vectors=([0.1] * DIMENSIONS,),
        prompt_tokens=4,
        total_tokens=4,
        attempts=1,
        provider="local",
    )
    monkeypatch.setattr("app.embeddings.BgeM3Client.embed", lambda self, texts: mock_batch)

    res = client.post("/api/v1/search", json={"query": "hydraulic pump", "modality": "all"})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "hydraulic pump"
    assert data["modality"] == "all"
    assert "video_segments" in data
    assert "document_chunks" in data
    assert isinstance(data["video_segments"], list)
    assert isinstance(data["document_chunks"], list)
    if data["video_segments"]:
        first = data["video_segments"][0]
        assert "refined_start_s" in first
        assert "refined_end_s" in first
        assert "seek_to_s" in first
        assert "asset_source_uri" in first


def test_seek_demo_endpoint(client):
    res = client.get("/demo/seek")
    assert res.status_code == 200
    assert "text/html" in res.headers.get("content-type", "")
    assert "video-player" in res.text
    assert "seek-hud" in res.text
    assert "Phase 2 Demo" in res.text


def test_generate_endpoint_disabled_when_search_disabled(database):
    app = create_app(Settings(ingest_enabled=False, search_enabled=False))

    def override():
        yield database

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        res = test_client.post("/api/v1/generate", json={"query": "test query"})
        assert res.status_code == 503
        assert "disabled" in res.json()["detail"]


def test_generate_endpoint_executes_and_validates_citations(client, monkeypatch):
    mock_batch = EmbeddingBatch(
        vectors=([0.1] * DIMENSIONS,),
        prompt_tokens=4,
        total_tokens=4,
        attempts=1,
        provider="local",
    )
    mock_vis_batch = VisualEmbeddingBatch(
        vectors=(([0.05] * VISUAL_DIMENSIONS),),
    )
    monkeypatch.setattr("app.embeddings.BgeM3Client.embed", lambda self, texts: mock_batch)
    monkeypatch.setattr("app.vision.SiglipVisualClient.embed_texts", lambda self, texts: mock_vis_batch)

    res = client.post("/api/v1/generate", json={"query": "hydraulic pump assembly procedure", "limit": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["query"] == "hydraulic pump assembly procedure"
    assert "answer" in data
    assert "abstained" in data
    assert "citations" in data
    assert isinstance(data["citations"], list)

    # Strictly verify Spec §16.6 Gate 3: No answer ever cites non-retrieved evidence
    valid_ids = {c["citation_id"] for c in data["citations"]}
    valid, invalid = validate_citations(data["answer"], valid_ids)
    assert valid is True, f"Answer cited invalid or non-retrieved citations: {invalid}"


def test_generate_endpoint_abstains_on_unanswerable_query(client, monkeypatch):
    mock_batch = EmbeddingBatch(
        vectors=([0.0] * DIMENSIONS,),
        prompt_tokens=4,
        total_tokens=4,
        attempts=1,
        provider="local",
    )
    mock_vis_batch = VisualEmbeddingBatch(
        vectors=(([0.0] * VISUAL_DIMENSIONS),),
    )
    monkeypatch.setattr("app.embeddings.BgeM3Client.embed", lambda self, texts: mock_batch)
    monkeypatch.setattr("app.vision.SiglipVisualClient.embed_texts", lambda self, texts: mock_vis_batch)

    res = client.post("/api/v1/generate", json={"query": "What is the nuclear reactor core pressure?", "limit": 5})
    assert res.status_code == 200
    data = res.json()
    assert data["abstained"] is True
    assert data["abstention_reason"] is not None
    assert "cannot answer this question based on the provided manufacturing evidence" in data["answer"]


def test_generate_stream_endpoint(client, monkeypatch):
    mock_batch = EmbeddingBatch(
        vectors=([0.1] * DIMENSIONS,),
        prompt_tokens=4,
        total_tokens=4,
        attempts=1,
        provider="local",
    )
    mock_vis_batch = VisualEmbeddingBatch(
        vectors=(([0.05] * VISUAL_DIMENSIONS),),
    )
    monkeypatch.setattr("app.embeddings.BgeM3Client.embed", lambda self, texts: mock_batch)
    monkeypatch.setattr("app.vision.SiglipVisualClient.embed_texts", lambda self, texts: mock_vis_batch)

    res = client.get("/api/v1/generate/stream?query=assemble+pump&limit=3")
    assert res.status_code == 200
    assert "text/event-stream" in res.headers.get("content-type", "")

    # Parse SSE events from response
    events = []
    for line in res.iter_lines():
        if line.startswith("data: "):
            payload = json.loads(line[6:])
            events.append(payload)

    assert len(events) >= 2
    types = [e.get("type") for e in events]
    assert "token" in types
    assert "done" in types
    done_event = [e for e in events if e.get("type") == "done"][0]
    assert "full_answer" in done_event or "query" in done_event
    assert "citations" in done_event


