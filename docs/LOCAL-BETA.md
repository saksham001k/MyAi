# KISS unified local assistant

KISS runs chat and tasks using your own local GGUF model. No KISS account, credit balance, paid provider or API key is required. Python dependencies and model/runtime downloads need internet for installation; local inference runs offline. Research needs internet and sends the search query/page request to public websites. No hosted LLM fallback is used by the web app.

## Start and check

From the project folder:

```sh
python3 scripts/local.py start
```

The Mac `Start-KISS.command` launcher uses the local virtual environment when available. Type your request and send it. KISS selects and loads an installed local model automatically; coding answers prefer a coding model and multi-step work prefers the general instruction model. Settings defaults to **8192 context** on this tested 16 GiB Mac with Automatic acceleration. Smaller machines may need smaller models/context. A 4096 context option is available for smaller memory budgets.

```sh
python3 scripts/local.py check
python3 scripts/local.py test
```

Fresh setup, or restoring missing Python dependencies:

```sh
python3 scripts/setup_local.py
```

Optional TypeScript analysis worker (requires Node/npm):

```sh
python3 scripts/setup_local.py --developer
```

Optional legacy interactive browser tools (not required for ordinary web research):

```sh
python3 scripts/setup_local.py --browser
```

Setup installs packages into `.venv`; it does not download model weights, create an account, configure paid APIs, or change your OS security settings. Normal app startup does not perform downloads.

## Work on a project

1. In the single composer, expand **Project access** and paste the absolute project path.
2. Describe the task, such as “Fix the failing tests in my project,” and send it.
3. For a trusted project, enable commands and supply its test command. With a test command configured, the agent gets a dedicated `run_tests` tool and final verification reruns that command if the working copy changed.
4. KISS copies supported source/text files into `data/tasks/<id>/project`. Model/runtime/data folders, common secrets, symbolic links and Git-ignored files are excluded. Dependencies such as `node_modules` are not copied. The beta copy budget is 500 files / 8 MB, with 200 KB per source file. Choose a smaller source root for larger projects.
5. Read the actual file diff and test output. **Apply reviewed changes** checks originals for conflicts, then copies only that review's changes back. New and deleted files appear in the review. **Undo** restores prior contents if they have not changed again.

Commands run as your OS user with an explicit working directory and reduced inherited environment. This source copy is not an OS sandbox: arbitrary programs can access the host. Enable commands only for trusted projects/tasks. File tools are scoped, but a general program cannot be confined by checking its command name.

Apply does not stage, commit, merge or push. A crash during a multi-file apply is not a filesystem transaction; before/after contents are retained in the task record for recovery. Failed or cancelled work is preserved. A task marked answered is a model response, not proof that a project goal was achieved.

## Research

Ask in the same composer, for example “Research the latest Python release using official sources.” The local model can search through best-effort free public endpoints and read public HTTP/HTTPS pages. A source URL can be supplied directly if search is blocked. Search candidates are not cited evidence; the agent must fetch pages before using source IDs.

The saved report includes retrieval URLs and dates. Full retrieved excerpts are retained in `sources.json` and visible in the interface. Citation-ID checks establish that a referenced source was fetched, not that every claim is entailed by it; review substantive claims. These free search endpoints have no uptime guarantee and can rate-limit/block requests. No CAPTCHA bypass is attempted.

Private/LAN/loopback addresses are excluded from public research. Redirects are revalidated and connections use the validated IP with HTTPS hostname verification. Downloads are bounded and compressed text is decoded with a size limit.

## Docs and personal response preferences

Use the single **Attach** button or drop UTF-8 text/code, text-based PDFs or images into the workspace. Each uploaded file appears once with its name, size, content availability, View and Detach controls. Text and image previews stay inside the app; PDF preview depends on browser support and includes Download original. Duplicate content with the same filename is deduplicated within the active conversation. The server extracts text, chooses a bounded set of passages relevant to the current question, and includes filename/page metadata. File cards distinguish text available to KISS, images available for editing, and stored-only attachments. The model receives server-owned extracted content, not client-supplied file descriptions.

Scanned PDFs need OCR, which is not implemented here. Images are stored but are not understood by the text chat model. This is basic document passage retrieval, not a persistent semantic knowledge library. Attachment references are stored per conversation in browser session storage and survive reloads in the same browser session. A new conversation starts with an empty attachment list. They are not a cross-device or permanent attachment library.

Settings also lets you save personal response instructions and a response-token budget locally. The selected model still has a finite context and hardware limit; there is no artificial daily message quota.

## Task persistence and stop

Task metadata and activity are saved under `data/tasks/`. Refreshing/reopening the browser recovers the task list and results. Leaving the browser does not cancel an active task. Closing the application stops its active work; restart marks unfinished work interrupted. Automatic action replay/resume after process restart is deliberately not implemented.

Stop cancels owned tool processes and unloads the local model to interrupt inference. Reload the model for your next task. No unrelated model service/process is terminated. Current sources/results survive.

## Architecture

- `myai/tasks.py`: shared local-model task coordinator, persisted events, verification and artifact output.
- `myai/project.py`: source copies, complete reviews, apply/undo and conflict checks.
- `myai/process.py`: bounded owned-process execution with cancellation.
- `myai/research.py`: account-free search and public page retrieval.
- `myai/documents.py`, `myai/uploader.py`: server-owned document extraction/context.
- `myai/preferences.py`: local response settings.
- `src/worker.ts`: optional single-request structural TypeScript worker used by the same Python-coordinated task; it makes no model calls.
- `web/js/tasks.js`: task start/list/status, evidence, diffs and outputs.

The older CLI remains available and has separate local Ollama support. Its agent generation now uses JSON directly rather than patch-generation instructions. Model fallback is explicit; worktree maps use the correct root; file reviews include new files; applying no longer auto-commits/squash-merges. The CLI worktree is preserved as recovery material. The web workflow does not require Ollama or a duplicate model download.

## Verification on the developer's Mac

- Existing Qwen3-4B-Q4_K_M, 8192 context, automatic Metal: read a broken Python function, fixed `a - b` to `a + b`, passed the supplied unittest, produced a review while preserving the original. The first real attempts exposed protocol/verification weaknesses that were fixed; this is a small acceptance test, not a broad model-quality benchmark.
- Same local model fetched Python.org and generated a three-fact report with source IDs and saved evidence.
- Public-page retrieval and free search fallback were exercised live. Search quality still varies.
- Browser UI exercised saved task retrieval, actual code diff, Apply and Undo on the disposable sample project.
- Automated suites cover protocol, task lifecycle, failed verification, source boundaries, conflicts/undo, document content, authentication, local preferences and TypeScript worker/worktree behavior.

## Still on the roadmap

OCR/vision, voice, native desktop automation, app connectors, a durable scheduler, robust automatic task resumption, broader large-project support, and new image/video hardware certification. Explicit editable memory and a persistent full-text document library are now available; broader semantic memory is still pending. Existing Studio adapters remain; this beta does not newly certify their output quality or speed.

## Unified prompt routing

There are no Chat/Code/Studio/Docs/Tasks mode tabs and no duplicate prompt/upload forms. The app uses a lightweight rule-based router over the user prompt, chosen project path and image presence. Routing makes no model call and needs no credits. It recognizes common coding, project, research, image and video requests; it is not a universal semantic planner. Ambiguous wording can be rephrased explicitly. Selection uses installed model names and sizes, not a capability benchmark. Missing local media dependencies are reported without silent hosted fallback or automatic downloads.

Image editing uses the first attached PNG/JPEG/WebP when the prompt requests a transformation. Text models cannot describe image contents. Video remains experimental and requires its Settings opt-in. A project path does not itself enable command execution.

All result types appear in the main workspace with one composer. Saved conversations, task records and creations remain their respective storage records; this release does not yet give cross-workflow conversational memory to project/media follow-ups. Reports and reviews preserve their existing evidence and Apply/Undo flow.

## Persistent memory and document library (11 September 2026)

Open **Memory & files** beside Settings. Save a titled fact explicitly, optionally scoped to the currently selected project. Use Edit to correct it or Forget to remove it from future saved context. Nothing is automatically learned from conversation history. Your existing response preferences still control answer style.

After attaching a document through the single Attach button, choose **Save to library** on its file card. The stored uploaded copy remains available across browser sessions and application restarts. Library source previews open through View source. Detaching from the current conversation does not forget a saved library item; forgetting a library item does not delete its original upload or detach an active attachment. These actions have separate, visible meanings.

SQLite FTS5 retrieves relevant excerpts locally, using words in your question. This is full-text matching, not semantic embeddings or perfect recall. Source labels such as [K1] identify real retrieved excerpts; the answer's **Saved context used** disclosure shows those excerpts live and source references in saved chats. Source IDs establish retrieval, not factual correctness. Project-scoped items are used only when that project is selected. Saved knowledge is supplied to local chat and project work; public web-research tasks do not automatically receive private saved facts.

The library checks source file metadata and content hashes, reindexes changed uploaded copies, and removes missing sources from retrieval. Editing/forgetting a memory invalidates old assistant messages dependent on that saved revision for future model context. Those old answers remain visible as history; Forget is not a transcript purge or secure disk erasure. Already-running responses cannot be changed retroactively, so library edits wait until the current operation finishes. Files originally uploaded from another folder are copies: changing the external original requires uploading and saving the new copy, then forgetting the old one.

Data lives in data/knowledge.sqlite3 and data/uploads/. The library supports 500 saved items, uses bounded excerpts, and makes no model/embedding API calls. Text PDFs are supported; OCR/scanned PDFs, semantic cross-language retrieval, a saved-project picker and safe task continuation remain future work.
