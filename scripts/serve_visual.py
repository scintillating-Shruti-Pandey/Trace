"""Local SigLIP 2 (google/siglip2-so400m-patch14-384) Visual Embedding Microservice.

Provides a fast, zero-cost, local HTTP endpoint for 1,152-d multimodal vision-text embeddings
on the user's RTX 4050 Laptop GPU. Listens on 0.0.0.0:8002 so both host scripts and Docker
containers (via http://host.docker.internal:8002) can query the visual lane.
"""

import argparse
import base64
import io
import sys
from contextlib import asynccontextmanager
from typing import Any

import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from PIL import Image as PILImage
from pydantic import BaseModel, Field
from transformers import AutoModel, AutoProcessor

MODEL_ID = "google/siglip2-so400m-patch14-384"
DIMENSIONS = 1152

_model: Any = None
_processor: Any = None


def get_model_and_processor():
    global _model, _processor
    if _model is None or _processor is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Loading {MODEL_ID} on {device} (FP16)...", flush=True)
        _processor = AutoProcessor.from_pretrained(MODEL_ID)
        _model = AutoModel.from_pretrained(
            MODEL_ID,
            dtype=torch.float16,
            device_map=device,
        )
        _model.eval()
        print(f"{MODEL_ID} loaded successfully on {device}.", flush=True)
    return _model, _processor


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_model_and_processor()
    yield


app = FastAPI(title="Trace Local SigLIP 2 Visual Service", lifespan=lifespan)


class TextEmbedRequest(BaseModel):
    texts: list[str] = Field(..., description="List of text queries to embed into 1,152-d visual space")


class ImageEmbedRequest(BaseModel):
    images_base64: list[str] = Field(..., description="List of base64-encoded JPEG/PNG images")


@app.get("/health")
def health():
    model, _ = get_model_and_processor()
    vram_mb = (
        round(torch.cuda.memory_allocated() / (1024**2), 2) if torch.cuda.is_available() else 0.0
    )
    vram_res = (
        round(torch.cuda.memory_reserved() / (1024**2), 2) if torch.cuda.is_available() else 0.0
    )
    return {
        "status": "ok",
        "model": MODEL_ID,
        "dim": DIMENSIONS,
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "vram_allocated_mb": vram_mb,
        "vram_reserved_mb": vram_res,
    }


@app.post("/v1/visual/embed_text")
def embed_text(req: TextEmbedRequest):
    if not req.texts:
        raise HTTPException(status_code=400, detail="Empty texts list")

    model, processor = get_model_and_processor()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        inputs = processor(
            text=req.texts,
            padding="max_length",
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out = model.get_text_features(input_ids=inputs["input_ids"])
            features = out.pooler_output if hasattr(out, "pooler_output") else out
            features = features / features.norm(dim=-1, keepdim=True)

        vectors = features.cpu().to(torch.float32).tolist()
        return {
            "model": MODEL_ID,
            "dim": DIMENSIONS,
            "vectors": vectors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/visual/embed_image")
def embed_image(req: ImageEmbedRequest):
    if not req.images_base64:
        raise HTTPException(status_code=400, detail="Empty images list")

    model, processor = get_model_and_processor()
    device = "cuda" if torch.cuda.is_available() else "cpu"

    try:
        pil_images = []
        for b64 in req.images_base64:
            img_bytes = base64.b64decode(b64)
            img = PILImage.open(io.BytesIO(img_bytes)).convert("RGB")
            pil_images.append(img)

        inputs = processor(
            images=pil_images,
            return_tensors="pt",
        ).to(device)

        with torch.no_grad():
            out = model.get_image_features(pixel_values=inputs["pixel_values"])
            features = out.pooler_output if hasattr(out, "pooler_output") else out
            features = features / features.norm(dim=-1, keepdim=True)

        vectors = features.cpu().to(torch.float32).tolist()
        return {
            "model": MODEL_ID,
            "dim": DIMENSIONS,
            "vectors": vectors,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8002)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
