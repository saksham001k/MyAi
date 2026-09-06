"""Small adapter over the authenticated local llama-server OpenAI-compatible API."""
from __future__ import annotations


class LocalInference:
    def __init__(self, engine):
        self.engine = engine

    def generate_patch(self, prompt, temperature=0.1, max_tokens=1024):
        messages = [
            {"role": "system", "content": (
                "Return only the replacement source block. Do not use markdown fences "
                "or explanations."
            )},
            {"role": "user", "content": prompt},
        ]
        return "".join(self.engine.stream(messages, temperature, max_tokens))


def generate_patch(engine, prompt, temperature=0.1, max_tokens=1024):
    return LocalInference(engine).generate_patch(prompt, temperature, max_tokens)
