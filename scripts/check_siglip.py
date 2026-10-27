import sys
import torch
import transformers

print(f"Python: {sys.version}")
print(f"Torch: {torch.__version__}, CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"Device: {torch.cuda.get_device_name(0)}")
    print(f"VRAM Allocated: {torch.cuda.memory_allocated() / (1024**2):.1f} MB")
    print(f"VRAM Reserved: {torch.cuda.memory_reserved() / (1024**2):.1f} MB")

print(f"Transformers: {transformers.__version__}")
siglip_classes = [c for c in dir(transformers) if "siglip" in c.lower()]
print(f"SigLIP classes in transformers: {siglip_classes}")
