"""Uses real PostgreSQL and Redis; writes roll back, never seeds the user's corpus."""

import os
from uuid import uuid4

import pytest
from app.config import Settings
from app.corpus import register
from app.datasets.register_remote import register_sources
from app.db import make_engine
from app.main import create_app, get_session
from app.models import Asset
from app.schemas import AssetCreate
from fastapi.testclient import TestClient
from sqlalchemy import text
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
    app = create_app(Settings(ingest_enabled=False))

    def override():
        yield database

    app.dependency_overrides[get_session] = override
    with TestClient(app) as test_client:
        yield test_client


def asset(database, kind):
    value = Asset(
        kind=kind,
        title="TEST FIXTURE ONLY",
        source_uri="test-fixture",
        storage_key="test/not-media",
        license="test-only",
        equipment_family="hydraulic",
        checksum_sha256=uuid4().hex * 2,
        duration_s=60 if kind == "video" else None,
    )
    database.add(value)
    database.flush()
    return value.id


def test_remote_registration_is_idempotent_and_not_ingestion(client, database):
    # Isolate the cap check inside this fixture's outer rollback-only transaction.
    database.execute(text("DELETE FROM remote_sources"))
    value = {
        "id": str(uuid4()),
        "repo": "test/source",
        "revision": "test-revision",
        "path": "test.mp4",
        "source_uri": "https://example.invalid/test.mp4",
        "license": "test-only",
        "category": "assembly",
        "duration_s": 200.0,
        "trial_group": "test-group",
        "verification": {"human_verified": False},
    }
    assert register_sources(database, [value])["created"] == 1
    assert register_sources(database, [value])["unchanged"] == 1
    assert client.get("/api/v1/remote-sources").status_code == 200
    items = client.get("/api/v1/remote-sources?limit=100").json()["items"]
    assert any(item["id"] == value["id"] for item in items)
    assert (
        database.scalar(
            text("SELECT count(*) FROM assets WHERE source_uri = :url"),
            {"url": value["source_uri"]},
        )
        == 0
    )
    with pytest.raises(ValueError, match="differs"):
        register_sources(database, [{**value, "duration_s": 201.0}])


def test_annotations_and_link_integrity(client, database):
    video, document = asset(database, "video"), asset(database, "document")
    segment = {"start_s": 5, "end_s": 15, "human_caption": "TEST CAPTION", "author": "test"}
    response = client.post(f"/api/v1/assets/{video}/segments", json=segment)
    assert response.status_code == 201, response.text
    segment_id = response.json()["id"]
    assert client.post(f"/api/v1/assets/{video}/segments", json=segment).status_code == 422
    assert (
        client.post(
            f"/api/v1/assets/{video}/segments", json={**segment, "start_s": 59, "end_s": 61}
        ).status_code
        == 422
    )
    assert client.post(f"/api/v1/assets/{document}/segments", json=segment).status_code == 422
    chunk = client.post(
        f"/api/v1/assets/{document}/chunks",
        json={
            "doc_type": "report",
            "section_path": "TEST",
            "text": "TEST PASSAGE",
            "token_count": 2,
        },
    )
    assert chunk.status_code == 201, chunk.text
    link = {
        "segment_id": segment_id,
        "chunk_id": chunk.json()["id"],
        "relation": "documents",
        "author": "test",
    }
    assert client.post("/api/v1/links", json=link).status_code == 201
    assert client.post("/api/v1/links", json={**link, "chunk_id": str(uuid4())}).status_code == 404
    verified = client.patch(
        f"/api/v1/segments/{segment_id}",
        json={
            "human_caption": "CORRECTED TEST CAPTION",
            "human_verified": True,
            "author": "reviewer",
        },
    )
    assert verified.json()["human_verified"] is True
    detail = client.get(f"/api/v1/assets/{video}").json()
    assert detail["segments"][0]["annotation_author"] == "reviewer"


def test_migrations_and_vector_dimensions(database):
    assert (
        database.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        == "0.8.0"
    )
    dimensions = database.execute(
        text("""
        SELECT c.relname, format_type(a.atttypid,a.atttypmod)
        FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
        WHERE c.relname IN ('vec_segment_text','vec_segment_visual','vec_chunk','vec_image')
        AND a.attname='embedding'
    """)
    ).all()
    assert dict(dimensions) == {
        "vec_segment_text": "vector(1024)",
        "vec_chunk": "vector(1024)",
        "vec_segment_visual": "vector(1152)",
        "vec_image": "vector(1152)",
    }


def test_ingestion_is_explicitly_disabled_and_health_honest(client):
    ready = client.get("/readyz")
    assert ready.status_code == 200, ready.text
    assert ready.json()["capabilities"] == {"media_ingest": False, "search": False}
    response = client.post(
        "/api/v1/ingest",
        json={
            "path": "not-present.mp4",
            "kind": "video",
            "title": "Test",
            "source_uri": "self-filmed",
            "license": "self",
            "equipment_family": "hydraulic",
        },
    )
    assert response.status_code == 503
    assert "MinIO" in response.json()["detail"]


def test_register_deduplicates_without_reupload(database, tmp_path):
    class FakeBlob:
        uploads = 0

        def put_file(self, path, key):
            assert path.read_text() == "TEST DATA " + marker
            self.uploads += 1

    marker = str(uuid4())
    (tmp_path / "fixture.txt").write_text("TEST DATA " + marker)
    settings = Settings(incoming_dir=tmp_path)
    manifest = AssetCreate(
        path="fixture.txt",
        kind="document",
        title="TEST ONLY",
        source_uri="fixture",
        license="test",
        equipment_family="cnc",
    )
    blob = FakeBlob()
    first = register(database, manifest, settings, blob)
    second = register(database, manifest, settings, blob)
    assert first["asset_id"] == second["asset_id"]
    assert second["deduplicated"] is True
    assert blob.uploads == 1
