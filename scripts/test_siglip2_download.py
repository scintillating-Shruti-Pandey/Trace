import sys
import time
import torch
from transformers import AutoModel, AutoProcessor

MODEL_ID = "google/siglip2-so400m-patch14-384"

print(f"Testing download & load of {MODEL_ID}...")
print(f"Initial CUDA VRAM: {torch.cuda.memory_allocated() / (1024**2):.1f} MB allocated, {torch.cuda.memory_reserved() / (1024**2):.1f} MB reserved")

t0 = time.perf_counter()
try:
    processor = AutoProcessor.from_pretrained(MODEL_ID)
    model = AutoModel.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.float16,
        device_map="cuda",
    )
    t1 = time.perf_counter()
    print(f"Model and processor loaded in {t1 - t0:.2f} s.")
    print(f"Loaded CUDA VRAM: {torch.cuda.memory_allocated() / (1024**2):.1f} MB allocated, {torch.cuda.memory_reserved() / (1024**2):.1f} MB reserved")

    # Test dummy text and image feature extraction
    from PIL import Image as PILImage
    dummy_img = PILImage.new("RGB", (384, 384), color=(128, 128, 128))
    
    inputs = processor(
        text=["test visual query for industrial assembly"],
        images=dummy_img,
        padding="max_length",
        return_tensors="pt",
    ).to("cuda")

    with torch.no_grad():
        image_features = model.get_image_features(pixel_values=inputs["pixel_values"])
        text_features = model.get_text_features(input_ids=inputs["input_ids"])
        
        # Normalize
        image_features = image_features / image_features.norm(dim=-1, keepdim=True)
        text_features = text_features / text_features.norm(dim=-1, keepdim=True)

    print(f"Image features shape: {image_features.shape}, dtype: {image_features.dtype}")
    print(f"Text features shape: {text_features.shape}, dtype: {text_features.dtype}")
    assert image_features.shape[-1] == 1152, f"Expected 1152 dim, got {image_features.shape[-1]}"
    assert text_features.shape[-1] == 1152, f"Expected 1152 dim, got {text_features.shape[-1]}"
    print("SUCCESS: Model output dimensions match PostgreSQL vector(1152) schema!")

except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
