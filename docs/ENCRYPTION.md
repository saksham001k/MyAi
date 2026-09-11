# Optional encrypted workspace (design)

This is a **design**, not a shipping encryption feature. Conversations, engine logs, document extracts, and workbench copies remain plaintext in `data/` until this is implemented and reviewed.

## Goal

Offer an opt-in encrypted workspace so a lost or borrowed pendrive does not expose chat history or ingested documents as ordinary files. Runtime binaries, UI assets, and GGUF weights stay unencrypted: they are large, already redistributable under their own licenses, and encrypting them does not protect against someone who can run the app.

## What would be encrypted

- `data/myai.sqlite3` and any backup copies
- `data/documents/`
- `data/workbench/`
- `data/engine.log` and creation job metadata

Not encrypted: `web/`, packaged Python, `runtime/`, `models/*.gguf`.

## Key and recovery

- The user supplies a workspace passphrase at first enablement. MyAi derives a 256-bit data key with scrypt (or Argon2id if an extra dependency is accepted).
- The data key encrypts files with AEAD (AES-256-GCM or ChaCha20-Poly1305). Each file has its own nonce.
- A **recovery key** (printable 32-byte secret) is shown once, wrapped with the same AEAD, and stored only if the user saves it outside the workspace.
- Losing both the passphrase and the recovery key means the ciphertext is unrecoverable. There is no backdoor, no cloud escrow, and no “forgot password” reset.
- Changing the passphrase re-wraps the data key; it does not re-encrypt payloads.

## Runtime semantics

- Encryption is off unless `data/workspace.keywrap` exists.
- On launch, MyAi asks for the passphrase before opening SQLite. A wrong passphrase fails closed; it does not create a second database.
- A locked workspace never writes plaintext fallback files.
- Safe eject still requires a clean shutdown so the last AEAD record is flushed. Abrupt removal can lose the tail of the last transaction, encrypted or not.

## Threats this would address

Casual inspection of the drive, copies of `data/`, and some unattended USB loss scenarios.

## Threats this would not address

Malware on the host, a user who already unlocked the workspace, browser extensions, malicious model/runtime binaries, cold-boot attacks against a running session, or backup copies made while unlocked.

## Implementation gate

Do not enable this until: a reviewed AEAD implementation exists (stdlib-only or an explicit extra), recovery UX is tested on a throwaway workspace, and backups of the wrapped key are documented in SETUP. Until then, treat local operation as **not** a secrecy guarantee, matching Architecture.
