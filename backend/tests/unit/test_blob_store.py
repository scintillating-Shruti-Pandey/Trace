"""Unit tests for S3/MinIO BlobStore adapter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from app.config import Settings
from app.stores.blob import BlobStore


@pytest.fixture
def settings():
    return Settings(
        blob_endpoint="http://127.0.0.1:9000",
        blob_bucket="test-trace",
        blob_access_key="test-key",
        blob_secret_key="test-secret",
    )


def test_blob_store_initialization(settings):
    with patch("boto3.client") as mock_client:
        store = BlobStore(settings)
        assert store.bucket == "test-trace"
        mock_client.assert_called_once()
        args, kwargs = mock_client.call_args
        assert args[0] == "s3"
        assert kwargs["endpoint_url"] == "http://127.0.0.1:9000"
        assert kwargs["aws_access_key_id"] == "test-key"
        assert kwargs["aws_secret_access_key"] == "test-secret"


def test_ensure_bucket_when_exists(settings):
    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3
        store = BlobStore(settings)
        store.ensure_bucket()
        mock_s3.head_bucket.assert_called_once_with(Bucket="test-trace")
        mock_s3.create_bucket.assert_not_called()


def test_ensure_bucket_creates_on_not_found(settings):
    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3
        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_s3.head_bucket.side_effect = ClientError(error_response, "head_bucket")

        store = BlobStore(settings)
        store.ensure_bucket()

        mock_s3.head_bucket.assert_called_once_with(Bucket="test-trace")
        mock_s3.create_bucket.assert_called_once_with(Bucket="test-trace")


def test_ensure_bucket_handles_race_condition(settings):
    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3
        not_found = {"Error": {"Code": "NoSuchBucket", "Message": "No Such Bucket"}}
        mock_s3.head_bucket.side_effect = ClientError(not_found, "head_bucket")
        already_owned = {"Error": {"Code": "BucketAlreadyOwnedByYou", "Message": "Owned"}}
        mock_s3.create_bucket.side_effect = ClientError(already_owned, "create_bucket")

        store = BlobStore(settings)
        store.ensure_bucket()  # Should not raise exception

        mock_s3.head_bucket.assert_called_once_with(Bucket="test-trace")
        mock_s3.create_bucket.assert_called_once_with(Bucket="test-trace")


def test_ensure_bucket_raises_on_unhandled_error(settings):
    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3
        auth_error = {"Error": {"Code": "403", "Message": "Forbidden"}}
        mock_s3.head_bucket.side_effect = ClientError(auth_error, "head_bucket")

        store = BlobStore(settings)
        with pytest.raises(ClientError):
            store.ensure_bucket()


def test_put_file(settings, tmp_path):
    dummy_file = tmp_path / "sample.mp4"
    dummy_file.write_bytes(b"DATA123")

    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3

        store = BlobStore(settings)
        store.put_file(dummy_file, "originals/asset1/sample.mp4")

        mock_s3.head_bucket.assert_called_once_with(Bucket="test-trace")
        mock_s3.upload_file.assert_called_once_with(
            str(dummy_file), "test-trace", "originals/asset1/sample.mp4"
        )


def test_ready_checks_list_buckets(settings):
    with patch("boto3.client") as mock_client_factory:
        mock_s3 = MagicMock()
        mock_client_factory.return_value = mock_s3

        store = BlobStore(settings)
        store.ready()
        mock_s3.list_buckets.assert_called_once()
