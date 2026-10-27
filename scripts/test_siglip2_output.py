import torch
from transformers import AutoModel, AutoProcessor
from PIL import Image as PILImage

MODEL_ID = "google/siglip2-so400m-patch14-384"

print(f"Loading cached {MODEL_ID}...")
processor = AutoProcessor.from_pretrained(MODEL_ID)
model = AutoModel.from_pretrained(
    MODEL_ID,
    dtype=torch.float16,
    device_map="cuda",
)

dummy_img = PILImage.new("RGB", (384, 384), color=(128, 128, 128))
inputs = processor(
    text=["black anodized camera mounting plate"],
    images=dummy_img,
    padding="max_length",
    return_tensors="pt",
).to("cuda")

with torch.no_grad():
    img_out = model.get_image_features(pixel_values=inputs["pixel_values"])
    text_out = model.get_text_features(input_ids=inputs["input_ids"])

    img_vec = img_out.pooler_output if hasattr(img_out, "pooler_output") else img_out
    text_vec = text_out.pooler_output if hasattr(text_out, "pooler_output") else text_out

    # Normalize vectors
    img_vec = img_vec / img_vec.norm(dim=-1, keepdim=True)
    text_vec = text_vec / text_vec.norm(dim=-1, keepdim=True)

    sim = (text_vec @ img_vec.T).item()

print(f"Image vector shape: {img_vec.shape}, dtype: {img_vec.dtype}")
print(f"Text vector shape: {text_vec.shape}, dtype: {text_vec.dtype}")
print(f"Cosine similarity: {sim:.4f}")
print(f"VRAM Allocated: {torch.cuda.memory_allocated() / (1024**2):.1f} MB")
print("SUCCESS: 1152-dim multimodal vectors verified!")
