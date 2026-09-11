# Set up MyAi

## 1. Start the application

Source checkout: Python 3.10+ and `python3 run.py` on Mac/Linux, or `python run.py` on Windows. There are no pip runtime dependencies.

Packaged app: run `MyAi` or `MyAi.exe` inside the complete extracted application folder. The `_internal` directory must remain next to the executable. Source launch scripts can also launch the packaged executable. On Mac/Linux, a downloaded archive may lose execute permissions; `chmod +x MyAi Start-MyAi.command start.sh` restores them for files you have chosen to run. Do not disable OS security protections globally.

The terminal prints a private session URL and opens it in your browser. Keep the terminal open. Closing the tab does not stop the application. Use Ctrl+C in the terminal to exit cleanly.

## 2. Add the inference runtime

Download a matching build from [official llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases). Select your OS, CPU architecture, and supported acceleration backend. Extract **the server and all companion libraries**, preserving the release's internal library layout. Put the server at the path shown in MyAi's setup hint:

| Computer | Expected server path |
| --- | --- |
| Apple Silicon Mac | `runtime/darwin-arm64/llama-server` |
| Intel Mac | `runtime/darwin-x86_64/llama-server` |
| Windows x64 | `runtime/windows-x86_64/llama-server.exe` |
| Linux x64 | `runtime/linux-x86_64/llama-server` |
| Linux ARM64 | `runtime/linux-arm64/llama-server` |

These are path conventions, not a tested compatibility guarantee. A single engine binary cannot run on every OS. Keep licenses shipped with the runtime. GPU builds may require compatible host drivers. On Mac/Linux the server must be executable. Launch `llama-server --version` from its runtime folder to verify missing-library issues before loading a model.

## 3. Add a model

Obtain a GGUF **instruction/chat** model compatible with your llama.cpp build and allowed by its license. Start with a small quantized model that fits available memory. MyAi currently supports one GGUF file per model; split models and multimodal projector setups are not supported by the loader.

Copy it into `models/`, use the source helper, or download a catalog entry from **Settings** after launch:

```bash
python3 scripts/import_model.py "/path/to/model.gguf" --sha256 PUBLISHER_SHA256
```

Replace `PUBLISHER_SHA256` with the publisher's actual 64-character SHA-256 digest. Omit `--sha256` if none is available; the helper then computes a checksum but cannot verify publisher authenticity. It checks the GGUF header, writes a temporary file, and only publishes the completed model. It will not overwrite an existing model.

The in-app catalog lists licenses and, for some models, a pinned publisher digest. Other entries fetch the Hugging Face LFS SHA-256 at download time. Interrupted downloads leave a `.part` file and resume with HTTP Range. Existing files that fail the digest are not overwritten.

Reload the UI after adding files. Settings shows measured RAM and a **conservative** model/context recommendation (file size × 1.25 plus KV-cache headroom). It is an estimate, not a guarantee. Pick your model and click **Load model**. Start with the recommended context, or 4096 and CPU. Try GPU only with a compatible runtime. Loading may take up to three minutes. The engine writes diagnostics to `data/engine.log`.

**Measure speed** runs a short prompt on the loaded model. Time-to-first-token and tokens/second come from llama.cpp `timings` when the server sends them. Otherwise the UI shows labeled wall-clock figures and will not invent a tokenizer throughput. These are session measurements, not product claims.

## 4. Chat and save

Send a prompt. Responses stream into the conversation and are saved when complete or interrupted. **Retry** appears on error or interrupted replies; **Regenerate** replaces the last complete assistant turn without duplicating the user message. Stop response is cooperative: it is acted on when the next engine chunk arrives, so long prompt processing can delay it. Export creates a Markdown download in the browser's normal download location. It is not automatically saved to the pendrive.

Context is budgeted: older complete turns may be dropped so the newest messages plus a reserved answer window fit the loaded context size. Token counts are estimated as UTF-8 bytes/4, not tokenizer tokens. If the engine still rejects the request, the UI explains whether to retry, start a new conversation, or load a larger context.

The **Docs** tab ingests local `.txt`, `.md`, and simple text-based PDFs, retrieves overlapping passages, and asks the model to cite them as `[source p.N]`. Scanned or heavily compressed PDFs are not extracted. This is lexical retrieval, not embedding RAG.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Missing runtime | Check exact platform directory, executable name and companion libraries |
| Model exits during load | Read `data/engine.log`; verify GGUF compatibility and free RAM |
| UI accessible but no answers | A real runtime and model are required; protocol tests and fixtures are not a fallback |
| Slow answers | Check the measured tok/s display after a run; try a smaller model; verify GPU build before enabling GPU mode |
| Session expired | Open the current URL printed by MyAi; tokens change each launch |
| Busy message | Wait for model load/generation, or stop the active response |
| Cannot save | Check free space and write access; preserve response text before closing |

Use only one MyAi instance per workspace. Do not open the same database from multiple computers or network shares. Phone/LAN access is deliberately unavailable in v0.1.
