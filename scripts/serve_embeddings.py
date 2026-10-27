"""Local BGE-M3 embedding microservice on host GPU.

Provides an OpenAI-compatible /v1/embeddings endpoint for local, offline,
zero-cost inference. Listens on 0.0.0.0:8001 so Docker containers can reach
it via http://host.docker.internal:8001/v1/embeddings.
"""

import argparse
from contextlib import asynccontextmanager

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer

MODEL_NAME = "BAAI/bge-m3"
DIMENSIONS = 1024

_model: SentenceTransformer | None = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading {MODEL_NAME} on {device} with safetensors...")
        _model = SentenceTransformer(
            MODEL_NAME,
            model_kwargs={"use_safetensors": True},
            device=device,
        )
        print("Model loaded successfully.")
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model()
    yield


app = FastAPI(title="Trace Local BGE-M3 Service", lifespan=lifespan)


class EmbeddingRequest(BaseModel):
    model: str = Field(default=MODEL_NAME)
    input: list[str] | str
    encoding_format: str = Field(default="float")


@app.get("/health")
def health():
    model = get_model()
    device = model.device.type if hasattr(model, "device") else "unknown"
    vram_mb = (
        round(torch.cuda.memory_allocated() / (1024**2), 2) if torch.cuda.is_available() else 0.0
    )
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "device": device,
        "dimensions": DIMENSIONS,
        "vram_allocated_mb": vram_mb,
    }


@app.post("/v1/embeddings")
def create_embeddings(req: EmbeddingRequest):
    if req.model != MODEL_NAME:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Requested model '{req.model}' unsupported; this server provides '{MODEL_NAME}'"
            ),
        )

    if isinstance(req.input, str):
        texts = [req.input]
    elif isinstance(req.input, list):
        texts = req.input
    else:
        raise HTTPException(status_code=400, detail="Input must be string or list of strings")

    if not (1 <= len(texts) <= 16):
        raise HTTPException(
            status_code=400,
            detail=f"Input batch size {len(texts)} outside permitted range 1-16",
        )

    for i, t in enumerate(texts):
        if not isinstance(t, str) or not t.strip():
            raise HTTPException(
                status_code=400, detail=f"Text item at index {i} is empty or not string"
            )
        if len(t.encode("utf-8")) > 4096:
            raise HTTPException(
                status_code=400,
                detail=f"Text item at index {i} exceeds 4096 UTF-8 bytes limit",
            )

    model = get_model()

    # Generate L2-normalized embeddings
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)

    # Estimate token count
    prompt_tokens = 0
    if hasattr(model, "tokenizer") and model.tokenizer is not None:
        try:
            tokens = model.tokenizer(texts, truncation=False)
            prompt_tokens = sum(len(ids) for ids in tokens["input_ids"])
        except Exception:
            prompt_tokens = sum(max(1, len(t) // 4) for t in texts)
    else:
        prompt_tokens = sum(max(1, len(t) // 4) for t in texts)

    data = []
    for idx, vec in enumerate(embeddings):
        float_vec = [float(x) for x in vec]
        data.append({"index": idx, "embedding": float_vec})

    return {
        "model": MODEL_NAME,
        "data": data,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "total_tokens": prompt_tokens,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Serve local BGE-M3 embedding service")
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host interface to bind (default: 0.0.0.0)"
    )
    parser.add_argument("--port", type=int, default=8001, help="Port to bind (default: 8001)")
    args = parser.parse_args()

    print(f"Starting BGE-M3 service on {args.host}:{args.port}...")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()
