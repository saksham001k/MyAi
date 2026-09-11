# Roadmap

## 0.1 — Portable chat foundation

Implemented: local chat UI, streamed answers, history/search/delete/export, manual model/context/GPU controls, dedicated runtime lifecycle, authenticated API, transactional storage, model import helper, platform launchers, tests, and build workflows.

Also in this branch: the production path is explicitly a dedicated llama.cpp/GGUF `llama-server` child (never a fixture). Protocol tests still stand in for CI. A skip-based real-model integration test runs only when `MYAI_REAL_INFERENCE=1` and a local runtime plus GGUF are present. Native package smoke now hits catalog and memory APIs. Physical pendrive checks in PENDRIVE.md remain unchecked hardware work.

Acceptance remaining: native builds on target computers, and the physical pendrive checks in PENDRIVE.md. Do not mark this release production-ready based only on protocol tests.

## 0.2 — Easier setup and measured performance

- [x] Verified runtime/model catalog with explicit license information (in-app `/api/catalog` plus `myai/catalog.json`; runtime pins stay in `runtimes.lock.json`).
- [x] Resumable downloads with publisher checksums and interrupted-download recovery (`myai/downloads.py`; catalog downloads resume `.part` files; pinned or Hugging Face LFS digests required).
- [x] Available-memory detection and conservative model/context recommendations (stdlib RAM snapshot; estimates, not guarantees).
- [x] Measured CPU/GPU calibration, time-to-first-token and tokens/second display (llama.cpp `timings` when present; otherwise labeled wall-clock / content-event metrics — not product claims).
- [x] Real-model integration tests and native package smoke tests (skip-based real GGUF test; packaged smoke extended). Still not a substitute for physical hardware runs.
- [x] Conversation retry/regenerate, context budgeting and clearer recovery flows (UTF-8 bytes/4 estimator; retry on error/interrupt; regenerate replaces the last assistant turn).

## 0.3 — Local documents and projects

- [x] PDF/text extraction and local retrieval with passage/page citations (UTF-8 text/Markdown and simple text-based PDFs; scanned/complex PDFs are refused honestly).
- [x] A fixed evaluation set checking whether cited passages support answers (`tests/fixtures/rag_eval.json`; lexical overlap, not an LLM judge).
- [x] Read-only repository indexing and explanations; proposed patches require review (`WorkspaceIndexer.explain`; workbench apply/undo unchanged).
- [x] Optional encrypted workspace **design** with documented recovery semantics (`docs/ENCRYPTION.md`). Not implemented.

## Later

Voice, compatible image models, Android, and authenticated LAN sharing. Each needs its own resource and privacy testing before a support claim.

## Comparison with PortableLM

Use identical computer, model, quantization, context and prompts. Compare cold launch, time to first token, token throughput, peak memory, offline setup/launch success and history recovery. Record versions and raw results. No speed or quality superiority claim is currently supported by measurements. The in-app measurement UI records **this run only**.
