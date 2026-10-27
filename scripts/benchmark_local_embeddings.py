"""Benchmark local BGE-M3 inference on RTX 4050 Laptop GPU.

Measures throughput (texts/sec), latency per batch, VRAM usage,
normalization, and deterministic output consistency.
"""

import math
import time
import torch
from sentence_transformers import SentenceTransformer

def run_benchmark():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device} ({torch.cuda.get_device_name(0) if device == 'cuda' else 'CPU'})")

    print("Loading BAAI/bge-m3 with safetensors...")
    t0 = time.perf_counter()
    model = SentenceTransformer("BAAI/bge-m3", model_kwargs={"use_safetensors": True}, device=device)
    load_time = time.perf_counter() - t0
    print(f"Model loaded in {load_time:.2f}s")
    vram_load = torch.cuda.memory_allocated() / (1024**2) if device == "cuda" else 0
    print(f"VRAM after load: {vram_load:.1f} MB")

    test_samples = [
        "Centrifugal pump bearing assembly procedure with torque specifications.",
        "Check shaft alignment and radial runout with dial indicator.",
        "Remove retaining ring using external circlip pliers and slide bearing off.",
        "Inspect seal face for thermal cracking, pitting, or chemical degradation.",
        "Apply threadlocker Loctite 243 to hex bolts and tighten in cross-pattern to 25 Nm.",
        "Vibration analysis indicates high 1X harmonics corresponding to impeller unbalance.",
        "Verify oil level in sight glass is between min and max operating marks.",
        "Emergency shut-off valve failed closed during hydraulic power unit test.",
    ]

    # Warmup
    _ = model.encode(test_samples[:2], normalize_embeddings=True)

    # Determinism test: encode twice, check exact or close similarity
    print("Testing determinism...")
    v1 = model.encode(test_samples[:2], normalize_embeddings=True)
    v2 = model.encode(test_samples[:2], normalize_embeddings=True)
    max_diff = (abs(v1 - v2)).max()
    print(f"Determinism max difference across runs: {max_diff:.8e}")
    assert max_diff < 1e-5, f"Determinism failure: max diff {max_diff}"

    # Normalization check
    print("Testing L2 normalization...")
    for vec in v1:
        norm = math.hypot(*vec)
        assert math.isclose(norm, 1.0, rel_tol=1e-4), f"L2 norm not close to 1: {norm}"
    print("L2 normalization verified (norm == 1.0 within 1e-4).")

    # Latency and throughput benchmarks across batch sizes
    print("\n--- Latency and Throughput ---")
    for batch_size in [1, 2, 4, 8]:
        batch = (test_samples * ((batch_size // len(test_samples)) + 1))[:batch_size]
        latencies = []
        for _ in range(5):
            t_start = time.perf_counter()
            _ = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            latencies.append(time.perf_counter() - t_start)
        avg_lat = sum(latencies) / len(latencies)
        throughput = batch_size / avg_lat
        print(f"Batch size {batch_size:2d}: {avg_lat*1000:6.1f} ms/batch ({throughput:5.1f} texts/sec)")

    peak_vram = torch.cuda.max_memory_allocated() / (1024**2) if device == "cuda" else 0
    print(f"\nPeak VRAM during benchmark: {peak_vram:.1f} MB")
    print("All benchmark checks PASSED successfully.")

if __name__ == "__main__":
    run_benchmark()
