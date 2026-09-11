# Pendrive stage (PD)

## Automated preparation

The portable build workflow now produces a combined bundle with native Apple Silicon Mac, Windows x64, and Linux x64 apps plus pinned inference runtimes. It publishes a prerelease only after native runtime startup and app/API/storage smoke checks pass on every platform. This still does not validate real model inference on every target computer.

When a successful portable release is available, close MyAi and run from your source checkout:

```bash
python3 scripts/prepare_pendrive.py --destination "/Volumes/YOUR_DRIVE/MyAi"
```

Replace YOUR_DRIVE with the actual mounted drive name. The destination must be a NEW folder. The helper downloads and verifies the bundle, copies installed models and saved conversations into Workspace, and keeps your original Mac folder. It never formats the drive or overwrites an existing destination. Close MyAi first so media outputs are not changing during the copy.

At the destination root, use Start-Mac.command, Start-Windows.bat, or Start-Linux.sh. Each calculates the shared Workspace location relative to itself. Changing drive letters or mount names does not require configuration. Unix launchers may need execution permission after a manual ZIP extraction; the helper preserves the ZIP's mode metadata. Some Linux mounts use noexec and cannot launch programs from that drive without changing mount configuration or copying the folder locally.

Supported initial architectures are Mac ARM64 and Windows/Linux x86_64. Windows/Linux runtimes are CPU builds. Linux binaries target Ubuntu 24.04-era systems; older libc versions and older CPUs may not work. Keep all Apps and Workspace subfolders together. Models are shared, native binaries are not. Physical pendrive and additional model testing remain deferred.

**Current gate: source implementation ready for setup; real-model and physical-drive validation pending.** A successful unit test or package build does not complete this stage.

## Before copying to the drive

1. Run MyAi from the computer's internal disk.
2. Install a runtime for the computer's exact OS/architecture and a compatible model.
3. Load it, ask several questions, stop a response, reopen a conversation and export it.
4. Disconnect from the internet and repeat a fresh app launch and model load.
5. Exit MyAi with Ctrl+C and wait for the process to stop.

## Prepare the drive

Use a writable drive with room for the whole application, runtime libraries, models, database, and spare space. FAT32 cannot hold individual files larger than 4 GiB; choose a suitable filesystem for the target computers. Do not reformat a drive containing data you need. USB storage speed mainly affects model loading; generation also depends on the computer's memory and processor/GPU.

Copy the **entire prepared folder**, including the package's `_internal` folder, `models`, `runtime`, and `data`. Do not copy a live database. For multiple operating systems, use separate native app folders and the `--root` option to point each at a shared workspace directory. Never run two applications against that shared workspace at once.

Example on a Mac, with paths adjusted for the actual drive:

```bash
"/Volumes/MY_DRIVE/Apps/MyAi-Mac/MyAi" --root "/Volumes/MY_DRIVE/Workspace"
```

The shared workspace holds `models/`, `runtime/<platform>/`, and `data/`. The UI assets remain bundled with each app. Runtime binaries are OS-specific; compatible model weights can be shared.

## Acceptance record

Record computer chip, RAM, OS, runtime version, model filename/checksum, context, GPU setting, and storage type. Complete each item on actual hardware:

- [ ] App launches from a folder containing spaces.
- [ ] Prepared app launches with internet disconnected.
- [ ] Real model produces a response without a cloud service.
- [ ] Stop, new chat, history, delete and export work.
- [ ] Close and reopen preserves conversations.
- [ ] Rename/move the folder; model discovery and history still work.
- [ ] Load and answer on the intended second computer with its matching runtime.
- [ ] Exit MyAi, safely eject, reconnect, and reopen successfully.
- [ ] Record startup time, time to first token, generation speed, and peak memory. The app can display TTFT/tok/s for a session when llama.cpp timings (or wall-clock fallbacks) are available; fill this row from the actual computer, not from CI.

Only after these checks should this release be described as pendrive-tested. Safe removal matters: transaction-based storage reduces normal corruption risks but cannot guarantee survival of an abrupt drive removal or failing flash media.
