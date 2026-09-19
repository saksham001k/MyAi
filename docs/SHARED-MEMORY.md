# Shared source memory with Earthma

Shared memory is an optional local connection. Start Earthma's memory service,
then launch MyAi using `Earthma/scripts/launch_myai_memory.py`. In MyAi, open
**Shared memory**, save a short fact, load an installed model, and ask about the
fact. Earthma Notes can read or edit the same record in the same memory space.
Use **Refresh facts** after editing in another app. Ordinary chat retains its
existing memory/history behavior; this integration is explicit in the new panel.

Example PowerShell, with sibling clones in your Projects directory:

```powershell
cd "$env:USERPROFILE\Documents\Projects\Earthma"
python scripts/memory_app.py serve --data D:/AI/earthma-memory --port 8877
# In a second terminal (or reuse an already running memory service):
python scripts/launch_myai_memory.py --data D:/AI/earthma-memory
```

The launcher checks the service before starting MyAi. It passes
`MYAI_EARTHMA_URL` and `MYAI_EARTHMA_TOKEN_FILE` only to the child app.
Custom deployments may set those environment variables directly before `run.py`.
MyAi accepts literal `http://127.0.0.1:port` URLs, refuses redirects and reads the
credential file afresh for each request. Do not publish that file or private
session URLs. The server uses MyAi's existing authentication and operation lock.

The panel loads the selected model on CPU, with 2048 context tokens. It changes
the app's loaded model. Memory answers use MyAi's own Engine, four matching facts
at most, no previous chat turns, temperature zero and 128 output tokens. Source
revisions are checked again after generation before publishing the answer. A
failed connection, changed source, cancellation, truncated or unfinished stream
returns an error. No matching record means no model invocation. Context fitting
uses MyAi's existing estimated token budget, not an exact tokenizer.

Use **Edit** to correct a fact and **Forget** to remove it from future retrieval.
Old conversations and exports remain. Memory spaces organize one user's facts;
they are not separate user permissions. The record list shows up to 100 facts.
Retrieval matches words; paraphrases without shared words can miss a fact.
Model output can be wrong even when the correct source is supplied. This adds
neither model-controlled tools nor automatic reading of other applications.

Local integration evidence and reproducible probes live in Earthma's
`docs/MYAI-MEMORY-RESULTS.md` and `scripts/myai_memory_probe.py`. Acceptance covers
short synthetic facts across two Qwen2.5 Coder configurations on Windows. It does
not establish universal model support, physical chip behavior or a speed win.

## Windows regression repairs found during integration

Project copies now preserve exact line endings when reading/writing reviewable
files, so unchanged CRLF text is not presented as an edit and undo restores exact
bytes. Verification commands use native Windows argument parsing instead of
POSIX backslash escaping; no shell is invoked. Tests cover both cases. A fixture
module was renamed to avoid shadowing Windows' built-in `math` module. A symlink
test explicitly skips only when Windows returns privilege error 1314; symlink
behavior is still exercised by Linux CI.
