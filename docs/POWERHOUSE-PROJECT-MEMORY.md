# Powerhouse project memory — first implementation

This increment supplies shared project requirements and handoffs to one local
worker. It does not yet run a parallel model team or automatically replay an
interrupted tool operation.

## Start and use

1. Restart Earthma's memory service with the updated source. Its existing
   `Start-Memory.ps1` uses `D:\AI\earthma-memory` on the prepared Windows PC.
2. Start MyAi through Earthma's `Start-MyAi-Memory.ps1`, which provides the
   localhost connection and service-owned credential file.
3. Load an installed local model. CPU acceleration is the tested baseline on
   the current i5/GT 710 computer; the acceptance probes used six CPU threads.
4. Open **Project memory**. Create a project with its name, absolute source
   folder, goal, and acceptance checks. A blank folder is allowed for project
   recall, but a linked coding task requires a matching source folder.
5. Select the saved project. Its source folder is copied into Project access.
   Subsequent project tasks receive the saved brief, current decisions,
   acceptance checks, and current handoff. Ordinary chat and public research
   retain their existing context behavior.
6. Inspect **Project memory** to read current state, edit the brief, correct or
   forget decisions, or ask the loaded model about the project.

Project selection survives a browser refresh in the same session. After an
application restart, select the project again from the saved list. Its data is
durable; automatic project selection from a natural-language “continue” request
is part of the later coordinator work.

## Saved data and current guarantees

Earthma owns the new `D:\AI\earthma-memory\powerhouse.sqlite3` database. The
existing facts database remains separate. Project updates, decision changes,
handoffs, and their audit events are transactional and revision checked.

Required project state is fetched by project ID instead of keyword search.
Different active decision values for the same subject produce an explicit
conflict. Correct a decision or forget an obsolete duplicate to resolve it.
Changing requirements or decisions excludes an outdated model handoff and
invalidates the derived current state. The audit history retains earlier data;
forgetting here removes it from future project context, not from backups.

Linked coding tasks save a report reference and SHA-256 hash, actual verification
status, model name, and a next action. Proposed file edits still need the existing
review/apply workflow. A handoff does not mean proposed edits have been applied.
If shared memory is unavailable or changed, local outputs survive and the task
shows a pending handoff. The payload remains in its local task record for later
reconciliation; an automatic pending-handoff retry interface is not yet supplied.

Project answers are buffered until the stream finishes and source revisions
are checked again. Truncated, cancelled, empty, stale, or wrong-project answers
are rejected. Context budgeting currently uses MyAi's estimated token count;
oversized required context is rejected instead of silently dropping records.
This feature does not establish perfect model recall or semantic retrieval.

## API

All routes retain the existing authenticated loopback access checks.

| MyAi route | Operation |
|---|---|
| GET `/api/powerhouse/projects` | List saved projects |
| POST `/api/powerhouse/projects` | Create name/workspace/goal/acceptance brief |
| GET `/api/powerhouse/projects/<id>` | Current structured context and manifest |
| POST `/api/powerhouse/projects/<id>` | Revision-checked brief/state update |
| POST `/api/powerhouse/projects/<id>/decision` | Create/edit/forget decision |
| POST `/api/powerhouse/projects/<id>/handoff` | Save handoff |
| POST `/api/powerhouse/ask` | Ask loaded model with project ID and question |
| POST `/api/tasks` with `shared_project_id` | Link a project task to shared context |

Earthma exposes the corresponding `/api/projects` routes plus project
`/context` and `/events`. Existing fact endpoints are compatible. Nonempty task
IDs make an identical handoff retry idempotent; a different payload for the same
task is rejected. Decision changes require the project revision and decision
revision. Cross-project decision mutations are refused.

## Evidence and remaining work

The implementation includes deterministic tests for revisions, two-writer
conflicts, context isolation, deletion, invalidation, restart, idempotency,
truncation, source changes, linked tasks, and offline saving.

Synthetic real-model acceptance passed nine checks: service restart, corrected
owner recall, next-action recall, persistence-requirement recall across the
installed 1.5B and 3B Qwen2.5 Coder models, structured conflict handling, and a
3B model conflict answer. These probes used isolated data, temporary model
copies, and MyAi's production Engine with the installed runtime path overridden.
They did not build a complete library app or measure a parallelism speed gain.

Browser checks exercised project creation, a decision, brief editing, a real
model answer, and selection/data restoration after refresh.

Next increments are the durable task graph, single-worker specialist sequencing,
runtime pool, measured adaptive concurrency, pending-operation reconciliation,
and the independent library-app acceptance fixture. Existing native saved facts
and Earthma keyword retrieval have not been migrated to a semantic index.
