# Local text runtime: proposed Windows CMD commands

Updated 2026-10-24: user-approved software stage installed in .venv-models.
Pip check and offline tiny random XLM-R GPU forward pass succeeded. No pretrained
weights downloaded. Installed logical size is 5.007 GB. Commands below document
the completed software setup; BGE-M3 weights still require separate approval.
Zero paid API usage. This is the text-embedding stage, not the complete project's
caption/ASR/image runtime. The isolated environment avoids modifying system Python
or Trace's backend environment. It does not by itself solve free caption generation.

## Download accounting

| Item | Transfer size | Status |
|---|---:|---|
| Official pinned BGE-M3 selected files | 2,293,315,801 bytes (2.293 GB) | Previously verified Hub metadata; no weights saved |
| CUDA PyTorch 2.6.0/cu124, CPython 3.12 Windows wheel | 2,532,302,369 bytes | Fresh official HTTP size header |
| Transformers 5.17.0 and 33 supporting packages | 46,210,254 bytes | Fresh PyPI wheel metadata; pinned URLs and SHA-256 |
| Software subtotal | **2,578,512,623 bytes (2.579 GB)** | Metadata-validated candidate, not runtime-tested |
| Software plus BGE-M3 | **4,871,828,424 bytes (4.872 GB)** | No binaries or weights fetched |
| SigLIP2 selected files | 4,582,795,867 bytes | Deferred; not included in this stage |
| Whisper large-v3 selected files | 3,090,835,702 bytes | Deferred; not included in this stage |

GB is decimal. These are transfer sizes, not installed or peak disk requirements.
The previous approval-review blocker cleared on the next user-authorized attempt.
Only registry JSON, wheel metadata and an HTTP HEAD were read. The software manifest
is [model-dependency-manifest.json](verification/model-dependency-manifest.json).
All active dependency version constraints were checked for Windows CPython 3.12.
This metadata planner is not pip's resolver; `pip check`, import and inference checks
remain required. Sizes exclude HTTP overhead, environment bootstrap and expanded disk
space. Reserve additional space for expanded CUDA libraries and temporary install files;
peak disk usage has not been measured. The former 8 GB estimate is withdrawn.

## Commands you can review

Run these in **CMD**, not inside Python. Do not run the installation section until
you approve the measured download amount. Only the software stage is installed below;
BGE-M3 weights need a separate approved fetch.

Create a separate environment (no network download):

```bat
cd /d D:\Trace
"%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv-models
.venv-models\Scripts\python.exe -m pip --version
```

Proposed installation sequence (downloads software; NOT yet validated as a complete
compatible environment):

```bat
.venv-models\Scripts\python.exe -m pip install --no-cache-dir --no-deps torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
.venv-models\Scripts\python.exe -m pip install --no-cache-dir --no-deps --require-hashes -r scripts\model-runtime-windows-py312.txt
.venv-models\Scripts\python.exe -m pip check
```

Torch 2.6.0/cu124 is an official older Windows build and meets the installed
Transformers .bin-loading version guard. This is a candidate baseline, not a claim
that it is the latest security-reviewed release or that inference has passed.
Transitive versions are pinned in the accompanying URL/hash manifest. The two install
commands intentionally use --no-deps to avoid unmeasured dependency downloads; all
selected dependencies are explicitly supplied by the manifest. Stop if pip check fails.
Do not use `--system-site-packages`: it would expose the crowded environment again.
Do not install torchvision/torchaudio, a CUDA toolkit, sentence-transformers or an
additional provider SDK for this initial text-only test unless a demonstrated need
arises. No generic global `pip install --upgrade` or driver update is justified yet.

Verification commands (no model download):

```bat
set HF_HUB_OFFLINE=1
set TRANSFORMERS_OFFLINE=1
.venv-models\Scripts\python.exe -c "import torch; print(torch.__version__); print('CUDA:', torch.cuda.is_available())"
.venv-models\Scripts\python.exe -c "from transformers import AutoModel, AutoTokenizer; print('Model classes imported')"
```

Stop on any error. Do not run `from_pretrained` without `local_files_only=True` for
an offline check: it can download weights. A separate approved model-fetch step must
use revision `5617a9f61b028005a4858fdac845db406aefb181` and only the selected files
in `verification/model-catalog-2026-10-24.json`, avoiding duplicate exports.

The environment will still need a tested dense pooling/normalization implementation,
GPU memory measurement and a separate local host-to-backend integration decision.
Successful imports do not prove BGE quality, indexing or full model fit.

Official build reference: [PyTorch previous versions](https://pytorch.org/get-started/previous-versions/).
