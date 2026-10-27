import sys
from huggingface_hub import hf_hub_download, list_repo_files

REPO_ID = "google/siglip2-so400m-patch14-384"
print(f"Checking repo files for {REPO_ID}...")

files = list_repo_files(REPO_ID)
print(f"Repo files count: {len(files)}")
safetensor_files = [f for f in files if f.endswith(".safetensors")]
print(f"Safetensor files: {safetensor_files}")
for f in files:
    if f.endswith(".json") or f.endswith(".safetensors"):
        print(f"  - {f}")
