# Roadmap

## 0.1 — Portable chat foundation

Implemented: local chat UI, streamed answers, history/search/delete/export, manual model/context/GPU controls, dedicated runtime lifecycle, authenticated API, transactional storage, model import helper, platform launchers, tests, and build workflows.

Acceptance remaining: real GGUF inference, native builds on target computers, and the physical pendrive checks in PENDRIVE.md. Do not mark this release production-ready based only on protocol tests.

## 0.2 — Easier setup and measured performance

- Verified runtime/model catalog with explicit license information.
- Resumable downloads with publisher checksums and interrupted-download recovery.
- Available-memory detection and conservative model/context recommendations.
- Measured CPU/GPU calibration, time-to-first-token and tokens/second display.
- Real-model integration tests and native package smoke tests.
- Conversation retry/regenerate, context budgeting and clearer recovery flows.

## 0.3 — Local documents and projects

- PDF/text extraction and local retrieval with passage/page citations.
- A fixed evaluation set checking whether cited passages support answers.
- Read-only repository indexing and explanations; proposed patches require review.
- Optional encrypted workspace design with documented recovery semantics.

## Later

Voice, compatible image models, Android, and authenticated LAN sharing. Each needs its own resource and privacy testing before a support claim.

## Comparison with PortableLM

Use identical computer, model, quantization, context and prompts. Compare cold launch, time to first token, token throughput, peak memory, offline setup/launch success and history recovery. Record versions and raw results. No speed or quality superiority claim is currently supported by measurements.
