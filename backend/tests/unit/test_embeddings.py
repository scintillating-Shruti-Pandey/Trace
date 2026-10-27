import json
import math

import httpx
import pytest
from app.config import Settings
from app.embeddings import MODEL, BgeM3Client, EmbeddingError
from pydantic import SecretStr


def response(count=1):
    return {
        "model": MODEL,
        "data": [
            {"index": i, "embedding": [3.0, 4.0] + [0.0] * 1022} for i in reversed(range(count))
        ],
        "usage": {"prompt_tokens": 7, "total_tokens": 7},
    }


def client(handler, **kwargs):
    return BgeM3Client(SecretStr("test-secret"), transport=httpx.MockTransport(handler), **kwargs)


def test_order_normalization_usage_and_wire_contract():
    def handler(request):
        assert request.url == "https://api.deepinfra.com/v1/openai/embeddings"
        assert request.headers["authorization"] == "Bearer test-secret"
        assert json.loads(request.content) == {
            "model": MODEL,
            "input": ["pump", "bearing"],
            "encoding_format": "float",
        }
        result = response(2)
        result["data"][0]["embedding"] = [1.0] + [0.0] * 1023
        return httpx.Response(200, json=result)

    result = client(handler).embed(["pump", "bearing"])
    assert result.vectors[0][:2] == (0.6, 0.8)
    assert result.vectors[1][0] == 1.0
    assert all(math.isclose(math.hypot(*v), 1) for v in result.vectors)
    assert (result.prompt_tokens, result.total_tokens, result.attempts) == (7, 7, 1)
    assert result.revision is None


@pytest.mark.parametrize("texts", [[], [""], ["  "], [None], "pump", ["x"] * 17, ["é" * 2049]])
def test_invalid_input_never_calls_network(texts):
    def handler(request):
        pytest.fail("Invalid inputs must not reach transport")

    with pytest.raises(ValueError):
        client(handler).embed(texts)


@pytest.mark.parametrize("key", [None, SecretStr(""), SecretStr(" ")])
def test_missing_key(key):
    with pytest.raises(EmbeddingError, match="DEEPINFRA_API_KEY"):
        BgeM3Client(key)


def test_settings_redacts_secret():
    settings = Settings(_env_file=None, deepinfra_api_key="private-token")
    assert "private-token" not in repr(settings)
    assert "private-token" not in settings.model_dump_json()


@pytest.mark.parametrize(
    "corruption",
    [
        "model",
        "missing_usage",
        "negative_usage",
        "boolean_usage",
        "short_vector",
        "nan",
        "zero",
        "boolean_vector",
        "duplicate_index",
        "wrong_index",
        "missing_row",
    ],
)
def test_invalid_provider_output(corruption):
    payload = response(2)
    row = payload["data"][0]
    if corruption == "model":
        payload["model"] = "another-model"
    elif corruption == "missing_usage":
        del payload["usage"]
    elif corruption == "negative_usage":
        payload["usage"]["total_tokens"] = -1
    elif corruption == "boolean_usage":
        payload["usage"]["prompt_tokens"] = True
    elif corruption == "short_vector":
        row["embedding"] = [1.0]
    elif corruption == "nan":
        row["embedding"][0] = float("nan")
    elif corruption == "zero":
        row["embedding"] = [0.0] * 1024
    elif corruption == "boolean_vector":
        row["embedding"][0] = True
    elif corruption == "duplicate_index":
        row["index"] = 0
    elif corruption == "wrong_index":
        row["index"] = 7
    elif corruption == "missing_row":
        payload["data"].pop()
    with pytest.raises(EmbeddingError, match="Invalid embedding"):
        client(lambda r: httpx.Response(200, content=json.dumps(payload))).embed(["a", "b"])


@pytest.mark.parametrize("status", [301, 401, 403, 429, 500, 503])
def test_http_errors_are_sanitized_and_not_replayed(status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            status, text="test-secret private input", headers={"Location": "https://example.com"}
        )

    with pytest.raises(EmbeddingError) as error:
        client(handler).embed(["private input"])
    assert str(error.value) == f"Embedding provider HTTP {status}"
    assert len(calls) == 1


def test_explicit_rate_limit_retry_is_bounded(monkeypatch):
    calls, sleeps = [], []
    monkeypatch.setattr("app.embeddings.time.sleep", sleeps.append)

    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "0"})

    with pytest.raises(EmbeddingError, match="HTTP 429"):
        client(handler, rate_limit_retries=2).embed(["pump"])
    assert len(calls) == 3
    assert sleeps == [0, 0]


def test_retry_success_records_attempts(monkeypatch):
    monkeypatch.setattr("app.embeddings.time.sleep", lambda _: None)
    replies = iter([httpx.Response(429), httpx.Response(200, json=response())])
    assert client(lambda r: next(replies), rate_limit_retries=1).embed(["pump"]).attempts == 2


def test_timeout_not_replayed_even_with_retries():
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("test-secret private input")

    with pytest.raises(EmbeddingError, match="not replayed") as error:
        client(handler, rate_limit_retries=2).embed(["pump"])
    assert "test-secret" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "body", [b"not JSON", b"x" * (2 * 1024 * 1024 + 1)], ids=["invalid-json", "oversized"]
)
def test_bad_response_body(body):
    with pytest.raises(EmbeddingError):
        client(lambda r: httpx.Response(200, content=body)).embed(["pump"])


@pytest.mark.parametrize("delay", ["nan", "-1", "11", "tomorrow"])
def test_invalid_or_long_retry_after_requires_rescheduling(delay):
    with pytest.raises(EmbeddingError, match="retry later"):
        client(
            lambda r: httpx.Response(429, headers={"Retry-After": delay}), rate_limit_retries=1
        ).embed(["pump"])


def test_local_endpoint_without_api_key_succeeds():
    def handler(request):
        assert request.url == "http://localhost:8001/v1/embeddings"
        assert "authorization" not in request.headers
        assert json.loads(request.content) == {
            "model": MODEL,
            "input": ["local test"],
            "encoding_format": "float",
        }
        return httpx.Response(200, json=response(1))

    local_client = BgeM3Client(
        api_key=None,
        endpoint="http://localhost:8001/v1/embeddings",
        transport=httpx.MockTransport(handler),
    )
    res = local_client.embed(["local test"])
    assert res.provider == "local"
    assert len(res.vectors) == 1
    assert len(res.vectors[0]) == 1024


@pytest.mark.parametrize(
    ("url", "is_local"),
    [
        ("http://localhost:8001/v1/embeddings", True),
        ("http://127.0.0.1:8001/v1/embeddings", True),
        ("http://host.docker.internal:8001/v1/embeddings", True),
        ("https://api.deepinfra.com/v1/openai/embeddings", False),
        ("https://custom-provider.example.com/v1/embeddings", False),
    ],
)
def test_local_endpoint_detection(url, is_local):
    from app.embeddings import is_local_endpoint

    assert is_local_endpoint(url) is is_local
