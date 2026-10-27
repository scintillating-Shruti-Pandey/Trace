"""Unit tests for arq ingest background worker settings and task handlers."""

from unittest.mock import MagicMock, patch

import pytest

from app.ingest.worker import WorkerSettings, ingest_asset


@pytest.mark.asyncio
async def test_ingest_asset_success():
    ctx = {
        "sessions": MagicMock(),
        "settings": MagicMock(),
        "blobs": MagicMock(),
    }
    manifest = {
        "path": "test.mp4",
        "kind": "video",
        "title": "Hydraulic Pump Check",
        "source_uri": "s3://test/pump.mp4",
        "license": "cc-by-4.0",
        "equipment_family": "hydraulic",
    }

    with patch("app.ingest.worker.register") as mock_register:
        mock_register.return_value = {
            "asset_id": "test-asset-123",
            "deduplicated": False,
            "status": "registered",
        }
        res = await ingest_asset(ctx, manifest)
        assert res["status"] == "registered"
        assert res["asset_id"] == "test-asset-123"
        assert "next_step" in res


@pytest.mark.asyncio
async def test_ingest_asset_value_error():
    ctx = {
        "sessions": MagicMock(),
        "settings": MagicMock(),
        "blobs": MagicMock(),
    }
    manifest = {
        "path": "test.mp4",
        "kind": "video",
        "title": "Invalid Asset",
        "source_uri": "s3://test/pump.mp4",
        "license": "cc-by-4.0",
        "equipment_family": "hydraulic",
    }

    with patch("app.ingest.worker.register") as mock_register:
        mock_register.side_effect = ValueError("corpus cap reached for video: 25")
        res = await ingest_asset(ctx, manifest)
        assert res["status"] == "failed"
        assert "corpus cap reached" in res["error"]


@pytest.mark.asyncio
async def test_ingest_asset_unexpected_exception():
    ctx = {
        "sessions": MagicMock(),
        "settings": MagicMock(),
        "blobs": MagicMock(),
    }
    manifest = {
        "path": "test.mp4",
        "kind": "video",
        "title": "Crash Asset",
        "source_uri": "s3://test/pump.mp4",
        "license": "cc-by-4.0",
        "equipment_family": "hydraulic",
    }

    with patch("app.ingest.worker.register") as mock_register:
        mock_register.side_effect = RuntimeError("database connection terminated")
        res = await ingest_asset(ctx, manifest)
        assert res["status"] == "failed"
        assert "Registration failed" in res["error"]


def test_worker_settings_attributes():
    assert ingest_asset in WorkerSettings.functions
    assert WorkerSettings.max_jobs == 2
    assert WorkerSettings.job_timeout == 1800
    assert WorkerSettings.keep_result == 7 * 24 * 3600
