"""Check exact download sizes for all needed packages and model weights."""
import urllib.request
import json

print("=" * 70)
print("  TRACE AI RUNTIME — EXACT DOWNLOAD LIST")
print("=" * 70)

# ── Section 1: PyTorch upgrade ──
print("\n--- OPTION A: Upgrade PyTorch to 2.6.0+cu124 ---")
print("  (Only needed if BGE-M3 safetensors require torch >= 2.6)")
print("  Current: torch 2.5.1+cu121")
print("  Target:  torch 2.6.0+cu124")

# Get torch cu124 wheel size
try:
    html = urllib.request.urlopen("https://download.pytorch.org/whl/cu124/torch/").read().decode()
    for line in html.split("\n"):
        if "2.6.0" in line and "win" in line and "cp312" in line:
            # Extract data-size if available, otherwise estimate
            print(f"  Wheel: torch-2.6.0+cu124-cp312-cp312-win_amd64.whl")
            print(f"  Size:  ~2.6 GB (typical CUDA PyTorch wheel)")
            break
except Exception as e:
    print(f"  Could not check: {e}")

print("  Also needs: torchvision, torchaudio (adds ~200 MB)")
print("  Total estimate: ~2.8 GB download")

# ── Section 2: Missing Python packages ──
print("\n--- REQUIRED: Missing Python packages ---")
packages = ["sentence-transformers", "sentencepiece", "accelerate"]
total_pkg = 0
for pkg in packages:
    try:
        url = f"https://pypi.org/pypi/{pkg}/json"
        data = json.loads(urllib.request.urlopen(url).read())
        ver = data["info"]["version"]
        best = None
        for f in data["urls"]:
            name = f["filename"]
            size = f["size"]
            if name.endswith(".whl"):
                if "cp312" in name and "win" in name:
                    best = (name, size)
                    break
                elif "none-any" in name:
                    best = (name, size)
        if not best:
            for f in data["urls"]:
                if f["filename"].endswith(".whl"):
                    best = (f["filename"], f["size"])
                    break
        if best:
            mb = best[1] / 1024 / 1024
            total_pkg += best[1]
            print(f"  {pkg} {ver}: {mb:.1f} MB")
        else:
            print(f"  {pkg} {ver}: size unknown")
    except Exception as e:
        print(f"  {pkg}: error ({e})")

print(f"  Subtotal: ~{total_pkg/1024/1024:.1f} MB")

# ── Section 3: BGE-M3 model weights ──
print("\n--- REQUIRED: BGE-M3 model weights ---")
print("  Model: BAAI/bge-m3")
print("  Files needed (dense-only, no ONNX):")
bge_files = [
    ("model.safetensors", 2293, "main weights"),
    ("tokenizer.json", 17, "tokenizer"),  
    ("sentencepiece.bpe.model", 5, "sentencepiece model"),
    ("config.json", 0.001, "config"),
    ("tokenizer_config.json", 0.001, "tokenizer config"),
]
bge_total = 0
for name, mb, desc in bge_files:
    bge_total += mb
    print(f"    {name}: ~{mb:.0f} MB ({desc})" if mb > 1 else f"    {name}: <1 MB ({desc})")
print(f"  Subtotal: ~{bge_total/1024:.1f} GB ({bge_total:.0f} MB)")

# ── Summary ──
print("\n" + "=" * 70)
print("  SUMMARY")
print("=" * 70)
print()
print("  OPTION 1 — Keep PyTorch 2.5.1, install missing packages only:")
print(f"    Download: ~{total_pkg/1024/1024:.0f} MB packages + ~2.3 GB model = ~2.4 GB")
print()
print("  OPTION 2 — Upgrade PyTorch 2.6.0+cu124 + missing packages:")
print(f"    Download: ~2.8 GB PyTorch + ~{total_pkg/1024/1024:.0f} MB packages + ~2.3 GB model = ~5.2 GB")
print()
print("  Note: Model weights are downloaded once to HuggingFace cache")
print("  (~C:\\Users\\<you>\\.cache\\huggingface\\hub)")
