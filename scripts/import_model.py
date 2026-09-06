#!/usr/bin/env python3
"""Copy an existing GGUF model without publishing a partial file."""
import argparse
import hashlib
import os
from pathlib import Path


def import_model(source, destination, expected=None):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source.suffix.lower() != ".gguf":
        raise ValueError("Expected a .gguf model")
    with source.open("rb") as stream:
        if stream.read(4) != b"GGUF":
            raise ValueError("File does not contain a GGUF header")
    if expected and (len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected.lower())):
        raise ValueError("SHA-256 must contain 64 hexadecimal characters")
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / source.name
    if target.exists():
        raise ValueError("A model with this name already exists; it will not be overwritten")
    partial = destination / (source.name + ".part")
    digest = hashlib.sha256()
    try:
        with source.open("rb") as inp, partial.open("xb") as out:
            while chunk := inp.read(4 * 1024 * 1024):
                digest.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        checksum = digest.hexdigest()
        if expected and checksum != expected.lower():
            raise ValueError("SHA-256 mismatch; model was not imported")
        os.replace(partial, target)
        return target, checksum
    except FileExistsError:
        raise ValueError("An import is already pending; inspect the .part file before retrying") from None
    except Exception:
        partial.unlink(missing_ok=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--sha256", help="Expected checksum from the model publisher")
    parser.add_argument("--destination", type=Path, default=Path(__file__).resolve().parents[1] / "models")
    args = parser.parse_args()
    try:
        target, checksum = import_model(args.source, args.destination, args.sha256)
        print(f"Imported: {target}\nSHA-256: {checksum}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
