# Powerhouse implementation progress — 2 October 2026

The baseline work and first shared project-memory increment are installed in the
existing local MyAi and Earthma applications. The next increment is reliable task
decomposition and sequential specialist execution; adaptive parallel model
execution is still pending.

## What was implemented

- A separate project-state database at `D:\AI\earthma-memory\powerhouse.sqlite3`.
- Project briefs with goal, acceptance checks, workspace, current state, and next action.
- Revisioned decisions, explicit conflicting values, correction and forgetting.
- Mandatory project retrieval by ID, independent of keyword matching.
- Source manifests and stale-result checks before publishing project answers.
- Durable handoffs with task/model identity, actual verification status, and report hashes.
- Idempotent identical handoff retries and rejection of conflicting writes.
- A Project memory panel for creating/selecting projects, editing the brief,
  managing decisions, and asking a loaded local model.
- Linked project tasks that receive saved context and save their result for a
  subsequent worker. Local results remain available if shared saving fails.
- A Windows request-rejection fix exposed by the baseline tests.

Application code is installed in:

- `C:\Users\Admin\Documents\Projects\MyAi`
- `C:\Users\Admin\Documents\Projects\Earthma`

The existing uncommitted diagnostic change in MyAi's server was preserved.
Source file snapshots, the initial diffs, and consistent database backups are
retained in this task's `work\baseline` directory. No model files were moved or
downloaded. Temporary copies were used for isolated real-model acceptance.

## Verification

| Check | Result | Scope |
|---|---|---|
| Current database backups | 3 backed up and restore-checked | Integrity and table-row counts compared in a separate restore location |
| MyAi installed-source suite | 135 tests; 130 passed, 5 skipped | Existing skips concern platform/symlink capability and opt-in inference |
| Earthma installed-source suite | 76 passed | Includes two-writer/two-handle revision protection and the project HTTP API |
| Real-model continuation | 9 checks passed | Restart, corrected owner, next task, persistence requirement across 1.5B/3B, explicit conflict |
| Qwen3 4B health | Passed | Basic load and completed generation only |
| Browser workflow | 5 checks passed; no page errors | Create project, decision, brief edit, real model answer, refresh recovery |

The native runtime identified itself as `0.4.1-dev`, build 11007, commit
`2f3fd0252`. Real-model probes ran on CPU with six threads and 2048 context.
These are limited correctness checks, not speed benchmarks or full library-app
acceptance. No concurrent model generation was tested in this increment.

## How to use it

Start or restart Earthma using its existing `Start-Memory.ps1`, then start MyAi
through Earthma's `Start-MyAi-Memory.ps1`. Load a local model, open **Project
memory**, and select or create a project. The current PC's tested baseline is CPU
inference. The full usage guide is installed as
`MyAi\docs\POWERHOUSE-PROJECT-MEMORY.md`.

Project data survives service/application restarts. The browser remembers the
selection on refresh in the same session; after restarting the application,
select the saved project from the list again. Natural-language automatic project
selection is later coordinator work.

## Current limits and next work

This first increment still uses one active model operation. It does not create a
parallel specialist team, automatically resume an interrupted command, migrate
all old saved facts, or implement semantic retrieval. A model can still answer
incorrectly even when supplied the correct state. Proposed edits continue to
use the existing review/apply workflow. A pending handoff is visible and retained
locally, with automated reconciliation planned later.

The next work package is:

1. Durable task graph, dependencies, ownership, and bounded retries.
2. Sequential planner/implementation/test/reviewer handoffs with independent
   acceptance checks for a small library application.
3. Separate runtime processes and scoped locks for real concurrent workers.
4. Resource admission and paired measurements to choose one, two, or more active
   workers according to task structure and machine capacity.
5. Recovery of interrupted work and release qualification.

The updated master plan remains `Powehouse.md` in the outputs directory and is
also included in MyAi's documentation. The release acceptance boxes remain
unchecked until their corresponding full capabilities pass.

## Desktop file and model-import increment

Settings now has Add models: full-path local GGUF import, background progress,
optional publisher SHA-256 verification, and no replacement of existing models.
The composer routes explicit Desktop HTML creation to a file task with a saved
path, download button, and durable report. Plain calculator requests use a tested
built-in template; other HTML requests use a local coding model. The first real
3B calculator attempt was incomplete, which prompted the template fallback.

Validation: MyAi 143 tests, 138 passed and 5 platform/optional tests skipped;
Settings browser import/completion/duplicate checks passed; calculator composer
and browser checks: 14 passed, no JavaScript errors. Details and current limits
are in `docs/DESKTOP-FILES-AND-MODELS.md`. Adaptive concurrent models remain pending.
