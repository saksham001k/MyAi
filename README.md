# KISS

**Your local model. Your projects. No mandatory AI account or credits.**

KISS is a local-first personal assistant by Saksham Katiyar. The **unified local beta** uses one composer with automatic selection among installed models. It includes persistent project/research tasks, reviewed file changes with undo, test verification, basic text/PDF understanding and local response preferences to the existing chat and Studio application.

It runs compatible GGUF models through its own llama.cpp process. The web app does not require an OpenAI account, API key, paid AI service or Ollama. Internet is needed for initial downloads and web research. A local model's quality and speed depend on your machine; no unlimited capability or commercial-agent parity is claimed.

## Start

```sh
python3 scripts/setup_local.py
python3 scripts/local.py start
```

On Mac, you can also double-click `Start-MyAi.command`. Existing models and runtime files are reused. If no runtime/model is installed, see [Setup](docs/SETUP.md); the optional Apple Silicon model helper is `python3 scripts/setup_mac.py`.

Choose a model and **Load selected model**. For project/research tasks on the tested 16 GiB Mac, use Settings → 8192 context → Automatic acceleration. Model loading does not require login.

## What you can do

- **Chat:** stream local answers, save conversations, copy/export them and customize response instructions.
- **Code:** discuss pasted/selected code and review edits to uploaded copies.
- **Tasks:** choose a project directory, let the agent read/edit a source copy, run a supplied test command, then review and apply changes with conflict detection and undo.
- **Research tasks:** search/read public webpages and save a report with retrieved source evidence using your local model.
- **Docs:** attach text/code or text-based PDFs and ask about extracted passages. Unsupported/scanned content is labeled honestly.
- **Studio:** existing image, image-to-image and experimental video adapters; separate compatible diffusion runtime/models are required.

Project commands run as your OS user; a working copy is not an OS sandbox. Enable command execution only for trusted projects and task instructions. Apply never implies Git commit or push.

Read the [local beta guide](docs/LOCAL-BETA.md) for exact setup, limits, architecture and acceptance evidence. It is the current capability reference; older release documents describe earlier milestones.

## Checks

```sh
python3 scripts/local.py check
python3 scripts/local.py test
```

Optional TypeScript source-analysis worker and developer checks:

```sh
python3 scripts/setup_local.py --developer
npm run typecheck
npm test
npm run build
```

Basic chat/project tools can start without extra Python packages. The standard setup enables PDF reading, image preprocessing and system diagnostics. Optional Playwright browser installation is separate: `python3 scripts/setup_local.py --browser`.

## Data and ownership

Conversations live in `data/myai.sqlite3`; tasks, evidence, working copies and reports live in `data/tasks/`. Models stay in `models/`; native runtimes stay in `runtime/`. These generated/private directories are Git-ignored. Personal planning is also excluded. Storage is local and unencrypted.

The HTTP interface binds to loopback, uses an automatic per-launch session token and checks origins. This session protection requires no user account. Stop the app before moving/copying its workspace. Back up important personal data independently of Git.

## Current acceptance and remaining work

A real local Qwen3-4B run fixed a small Python test project and passed its supplied test. Another run read Python.org and saved a cited report. These are limited hardware acceptance examples, not a claim of broad autonomous reliability. Automated tests cover API/protocol and lifecycle behavior.

Long-term memory, OCR, chat vision, voice, native desktop control, app connections, background scheduling and robust restart resumption remain on the roadmap. Image/video quality and physical pendrive portability are not newly certified by this release.

## Credits

Inspired by the portable-workspace concept in [PortableLM](https://github.com/orailnoor/PortableLM). Application code is an original MIT-licensed implementation; see [LICENSE](LICENSE). Inference uses [llama.cpp](https://github.com/ggml-org/llama.cpp); diffusion uses [stable-diffusion.cpp](https://github.com/leejet/stable-diffusion.cpp). Runtime/model licenses and compatibility requirements remain separate. No pretrained model weights or runtime binaries belong in source commits.

### Memory and files

Use **Memory & files** to save, edit, inspect or forget explicit facts. On an uploaded file, choose **Save to library** for local full-text retrieval in future conversations. Saved context is cited and remains on this computer. See [the usage guide](docs/LOCAL-BETA.md) for source freshness, project scope and deletion behavior.
