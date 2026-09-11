# Architecture and boundaries

The v0.1 implementation uses Python standard library plus plain bundled HTML/CSS/JavaScript, instead of the originally proposed Go/React stack. This keeps the first release testable without application dependencies. PyInstaller provides a native distribution option; changing the frontend or service later does not require replacing the model directory or conversation schema.

Browser requests go to an authenticated loopback-only API. The application owns one llama-server child on a separate loopback port, checks readiness and calls `/v1/chat/completions` with SSE streaming. The engine adapter ignores configured HTTP proxies. It never connects to a pre-existing Ollama or llama.cpp server and never terminates unrelated processes.

The UI receives newline-delimited JSON, renders model output as text (not executable HTML), and retrieves saved conversations from SQLite. A single operation lock prevents model switches or deletion during generation. The database uses transactions, foreign keys and full synchronization. Completed and interrupted assistant messages carry different statuses; only completed messages enter later context.

Session tokens are random per application launch. The initial token is passed in a URL fragment, removed from the visible URL and kept in tab-scoped session storage. API calls require the token, the expected Host header, and a same-origin Origin when supplied. Request bodies are bounded to 25 MB (needed for document uploads). Static routes are an explicit allowlist; arbitrary workspace paths are not served. No permissive CORS header is sent.

Security scope: this protects against accidental LAN exposure and unauthenticated web requests. It does not protect against malware, a user with filesystem access, malicious model/runtime binaries, or browser extensions on the host. Conversations and engine diagnostics are not encrypted. Do not treat local operation as a guarantee of host secrecy.

Known limits: one active generation; cancellation waits for the next chunk; a rare port allocation race causes startup failure rather than attachment to another service; cross-platform native runtime compatibility and abrupt-removal durability require physical testing. Context is budgeted with a UTF-8 bytes/4 estimate that drops older turns and never the latest user message; that is not a tokenizer. Catalog downloads are optional HTTPS pulls with publisher checksums; they are not used during chat. Document retrieval is lexical (not embedding RAG) and only supports extractable text PDFs. Conversations are not encrypted; see [ENCRYPTION](ENCRYPTION.md) for the optional design.

Protocol tests inject an HTTP fixture in place of llama-server. `run.py` never uses that fixture: it starts a dedicated llama.cpp child and calls `/v1/chat/completions`. Set `MYAI_REAL_INFERENCE=1` to run the optional real-GGUF test when a runtime and model are installed. Passing unit tests does not validate model quality or speed.

Protocol reference: [llama.cpp server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server). Packaging reference: [PyInstaller 6.16](https://pyinstaller.org/en/v6.16.0/usage.html).
