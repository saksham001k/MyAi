"""Small local-only preferences. Never contain provider keys or credentials."""
import json
import os
from pathlib import Path

DEFAULTS = {'instructions': '', 'max_output_tokens': 2048}


class Preferences:
    def __init__(self, root):
        self.path = Path(root) / 'preferences.json'
    def get(self):
        try:
            return {**DEFAULTS, **json.loads(self.path.read_text(encoding='utf-8'))}
        except FileNotFoundError:
            return dict(DEFAULTS)
    def save(self, body):
        instructions = body.get('instructions', '')
        tokens = body.get('max_output_tokens', 2048)
        if not isinstance(instructions, str) or len(instructions) > 4000:
            raise ValueError('Personal instructions must be up to 4,000 characters.')
        if type(tokens) is not int or tokens not in (512, 1024, 2048, 4096, 8192):
            raise ValueError('Choose a supported output budget.')
        value = {'instructions': instructions, 'max_output_tokens': tokens}
        temp = self.path.with_suffix('.tmp')
        temp.write_text(json.dumps(value), encoding='utf-8')
        os.replace(temp, self.path)
        return value
