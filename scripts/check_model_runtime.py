"""Offline runtime check: no pretrained weights, API calls or dataset reads."""

import json
import os
import time

os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

started = time.monotonic()
import torch  # noqa: E402
import transformers  # noqa: E402
from transformers import AutoModel, XLMRobertaConfig  # noqa: E402

imports_s = time.monotonic() - started
if not torch.cuda.is_available():
    raise RuntimeError("CUDA unavailable: stop before downloading model weights")

# Tiny random model checks the BGE backbone code path; not BGE inference or quality.
config = XLMRobertaConfig(
    vocab_size=128,
    hidden_size=32,
    num_hidden_layers=1,
    num_attention_heads=4,
    intermediate_size=64,
    max_position_embeddings=64,
)
model = AutoModel.from_config(config).eval().to("cuda")
with torch.inference_mode():
    result = model(
        input_ids=torch.tensor([[0, 5, 7, 2]], device="cuda"),
        attention_mask=torch.ones((1, 4), dtype=torch.long, device="cuda"),
    ).last_hidden_state
    assert result.shape == (1, 4, 32)
    assert torch.isfinite(result).all().item()
torch.cuda.synchronize()
print(
    json.dumps(
        {
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "cuda_runtime": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "imports_seconds": round(imports_s, 3),
            "tiny_random_backbone_shape": list(result.shape),
            "finite": True,
            "pretrained_weights_loaded": False,
            "offline": True,
        },
        indent=2,
    )
)
