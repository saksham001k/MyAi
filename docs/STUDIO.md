# Coding, Images and Video

This update adds usable application integrations and optional download helpers. The new model packs are **not downloaded by updating Git**, and their performance has not been verified on the target Mac. The existing Qwen3 chat has been observed producing a real response on the user's M4; image/video inference and the added coding models remain hardware-unverified. User testing is deferred.

## Code workspace

The Code tab uses a coding-specific instruction and the selected text model. It can explain pasted code, draft implementations, and suggest tests. It does not execute code, edit repositories, or pretend to have tested its answers. Fenced code blocks and bold text render with DOM text nodes, never model-generated HTML. Choose a downloaded coding model in the regular model selector and Load model.

Optional downloads, when ready:

```bash
python3 scripts/setup_models.py code-small code
```

`code-small` installs Qwen2.5-Coder-1.5B-Instruct Q4_K_M; `code` installs the 3B variant. These are deliberately modest starting options for 16 GB unified memory, not a claim of best available coding quality. The 3B publisher lists a Qwen Research license; review each publisher's model license for the intended use. Existing GGUF chat models continue to work. Only one text model is loaded at once.

## Image workspace

Two preset adapters: Stable Diffusion 1.5 (512 × 512) and SDXL Base 1.0 (768 × 768). SDXL is heavier. Each uses a single checkpoint containing the standard required components. The app runs stable-diffusion.cpp's `sd-cli` with explicit arguments, a bounded step count and seed, and a unique output folder.

```bash
python3 scripts/setup_models.py image --runtime
# Optional larger image model:
python3 scripts/setup_models.py image-xl
```

The runtime helper searches official stable-diffusion.cpp releases for a checksummed macOS ARM64 binary. It preserves companion libraries and creates a portable launcher. If upstream does not provide a matching checksummed artifact, setup **stops honestly**: it does not silently install an unrelated binary or claim success. In that case, a compatible `sd-cli` and its libraries must be built or supplied under `runtime/darwin-arm64/`; this remains a setup limitation, not a completed one-click guarantee. There is no automatic build-from-source fallback yet.

## Video workspace — experimental

The adapter targets Wan2.1 T2V 1.3B with its matching Wan VAE and quantized UMT5 encoder. It produces an AVI file, available for download. The first preset deliberately requests 256 × 256, 17 frames and CPU offload; this is a small experimental generation, not a promise of smooth, high-quality or real-time video. A 16 GB machine may still run out of memory or take a long time. No actual video generation benchmark has been run here.

```bash
python3 scripts/setup_models.py video --runtime
```

The UI requires explicit experimental opt-in before submitting a video job. There is no sound generation or built-in AVI playback. Download the result and use a compatible video player. Runtime option compatibility follows the upstream CLI and must be checked with the installed build.

## Shared behavior

- Chat model memory is released before diffusion begins; reload your chat model afterward.
- One expensive operation runs at a time. Missing models are checked before unloading chat.
- Running status is real job state; no invented progress percentage.
- Cancel terminates only MyAi's child diffusion process.
- Each generation has metadata, output and engine diagnostics in `data/creations/<id>/`.
- A 30-minute timeout prevents an indefinitely running generation.
- Restart marks abandoned jobs interrupted. Completed outputs remain accessible.
- Download routes require the session token. The API never accepts arbitrary commands or output paths.
- Download helpers use publisher SHA-256 metadata and immutable revision URLs, and support resuming partial files. They do not accept gated-model terms on the user's behalf.

## Sources

- [Qwen coding models](https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF)
- [SD checkpoint instructions](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/sd.md)
- [Wan component and CLI instructions](https://github.com/leejet/stable-diffusion.cpp/blob/master/docs/wan.md)
- [Diffusion runtime source and supported backends](https://github.com/leejet/stable-diffusion.cpp)

Downloads and output consume disk space. The pendrive stage and physical hardware acceptance checks are still deferred; these integrations do not certify portability, model quality, or performance.
