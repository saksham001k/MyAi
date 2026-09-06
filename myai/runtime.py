"""Resolve packaged executables without flattening their companion libraries."""
import json


def executable(folder, name):
    manifest = folder / "runtime.json"
    if manifest.is_file():
        mapping = json.loads(manifest.read_text())
        relative = mapping.get(name)
        if relative:
            path = (folder / relative).resolve()
            if not path.is_relative_to(folder.resolve()):
                raise ValueError("Runtime manifest points outside its directory")
            return path
    return folder / name
