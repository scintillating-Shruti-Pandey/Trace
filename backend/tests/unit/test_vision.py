"""Unit tests for SigLIP 2 visual embedder client."""

import httpx
import pytest
from app.vision import DIMENSIONS, MODEL, SiglipVisualClient, VisualEmbeddingError


def _mock_transport(status_code: int = 200, vectors: list | None = None):
    if vectors is None:
        vectors = [[0.1] * DIMENSIONS]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=status_code,
            json={"model": MODEL, "dim": DIMENSIONS, "vectors": vectors},
        )

    return httpx.MockTransport(handler)


def test_siglip_client_embed_text_success():
    transport = _mock_transport()
    client = SiglipVisualClient(transport=transport)
    batch = client.embed_texts(["test industrial query"])

    assert len(batch.vectors) == 1
    assert len(batch.vectors[0]) == 1152
    assert batch.model == MODEL
    assert batch.dim == 1152


def test_siglip_client_embed_image_success():
    transport = _mock_transport()
    client = SiglipVisualClient(transport=transport)
    batch = client.embed_images([b"fake_image_bytes"])

    assert len(batch.vectors) == 1
    assert len(batch.vectors[0]) == 1152


def test_siglip_client_rejects_empty_input():
    client = SiglipVisualClient()
    with pytest.raises(ValueError, match="cannot be empty"):
        client.embed_texts([])

    with pytest.raises(ValueError, match="cannot be empty"):
        client.embed_images([])


def test_siglip_client_rejects_invalid_dim():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            json={"model": MODEL, "dim": 512, "vectors": [[0.1] * 512]},
        )

    client = SiglipVisualClient(transport=httpx.MockTransport(handler))
    with pytest.raises(VisualEmbeddingError, match="Expected 1152-d vector"):
        client.embed_texts(["test"])


def test_siglip_client_rejects_nan_inf():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=200,
            headers={"content-type": "application/json"},
            content=b'{"model": "google/siglip2-so400m-patch14-384", "dim": 1152, "vectors": [[NaN]]}',
        )

    client = SiglipVisualClient(transport=httpx.MockTransport(handler))
    with pytest.raises(VisualEmbeddingError):
        client.embed_texts(["test"])
