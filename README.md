# MyAi

**Your models. Your conversations. Your workspace.**

MyAi is a local-first AI chat application by Saksham Katiyar. It runs a compatible GGUF model through a dedicated llama.cpp server and keeps conversations beside the app, ready to move with the workspace.

**Status: v0.1.0 source implementation. Real-model and physical pendrive acceptance testing are still required.** This repository contains working application code, tests, launchers, and packaging workflows—not pretrained model weights or runtime binaries. It does not claim to outperform PortableLM yet.

## What works in this version

- Browser chat interface with streamed text, response cancellation, copy, and Markdown export.
- Persistent conversations, title search, and deletion using SQLite.
- Local GGUF model discovery, model loading/unloading, context and GPU-layer controls.
- Isolated llama-server process with loopback binding and a per-launch API key.
- Authenticated application API, strict origin checks, no external UI assets or cloud fallback.
- Relative workspace layout, transactional saves, checksum-verified model import helper.
- Source launchers for Mac, Windows and Linux; native app packaging workflow.

## First run on Mac or Linux

```bash
git clone https://github.com/saksham001k/MyAi.git
cd MyAi
python3 run.py
```

The interface opens even before a model is installed and explains which files are missing. **Source mode needs Python 3.10+.** On Windows, use `python run.py` or `Start-MyAi.bat`.

For actual AI answers, follow [SETUP](docs/SETUP.md) to add a compatible llama.cpp runtime and GGUF model. No downloads happen automatically. Once prepared, chat does not require internet access.

## Workspace layout

| Path | Purpose |
| --- | --- |
| `run.py`, `myai/` | Application, API, inference adapter and storage |
| `web/` | Bundled interface, with no CDN dependencies |
| `models/` | Your compatible `.gguf` models; never committed |
| `runtime/<platform>-<architecture>/` | `llama-server` plus required libraries; never committed |
| `data/` | Chat database and engine diagnostics; never committed |
| `scripts/` | Model import, environment checks and package assembly |
| `tests/` | API, inference protocol and portability tests |
| `docs/` | Setup, architecture, limitations and pendrive acceptance |

## Development checks

```bash
python3 -m unittest discover -s tests -v
python3 scripts/doctor.py
```

`doctor.py` is expected to report missing items until your runtime and model are installed. Tests use a protocol fixture, not real AI; passing them does not validate model quality or speed.

## Packaged builds

Run **Actions → Package portable app → Run workflow**. The workflow builds a native application for each runner platform; download the artifact matching your computer. The package includes Python internally, but **you must still add the llama.cpp runtime and a model**. It is not an all-in-one installer yet. Builds are not notarized or production-certified. Architecture is included in each artifact name. Intel Mac and ARM Windows builds require matching build runners and are not covered by the initial matrix.

Keep the entire extracted directory, including `_internal`, together. See [pendrive preparation](docs/PENDRIVE.md) before moving it.

## Scope and next steps

The first target is reliable portable chat. Document RAG, repository indexing, voice, Android, automatic model recommendations, resumable downloads, encrypted storage, and authenticated LAN sharing are **not implemented**. See [ROADMAP](docs/ROADMAP.md) for acceptance gates.

MyAi stores data locally, but does not make the host computer trustworthy or prevent operating-system/browser caches. Storage is not encrypted. Stop MyAi before ejecting or copying its workspace.

## Credits

Inspired by the portable-workspace concept in [PortableLM](https://github.com/orailnoor/PortableLM). MyAi's application code is an original implementation. Inference is provided by [llama.cpp](https://github.com/ggml-org/llama.cpp); its binaries and models have their own licenses and compatibility requirements. No PortableLM source or model weights are included.

MyAi application code is MIT licensed. See [LICENSE](LICENSE).

## Upload and edit project files

MyAi now accepts UTF-8 text/code uploads and folder uploads, includes selected files in local chat context, and offers reviewed coding changes with Apply, Undo, and individual file downloads. Open **Project files · Upload and edit**. See [Workbench guide](docs/WORKBENCH.md) for limits and usage. This edits uploaded copies; it does not run terminal commands.
