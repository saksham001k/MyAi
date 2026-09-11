import os
import unittest
from pathlib import Path

from myai.engine import Engine, platform_tag


@unittest.skipUnless(os.environ.get("MYAI_REAL_INFERENCE") == "1",
                     "Set MYAI_REAL_INFERENCE=1 with a local llama-server and GGUF to run this.")
class RealGgufInferenceTests(unittest.TestCase):
    def test_load_real_runtime_and_stream_one_token(self):
        root = Path(__file__).resolve().parents[1]
        engine = Engine(root)
        models = engine.models()
        self.assertTrue(engine.binary.is_file(), f"llama-server missing for {platform_tag()}")
        self.assertTrue(models, "No GGUF in models/")
        engine.start(models[0]["name"], context=2048, gpu_layers=0)
        try:
            text = "".join(engine.stream(
                [{"role": "user", "content": "Reply with the single word: ok"}],
                temperature=0, max_tokens=8))
            self.assertTrue(text.strip())
            self.assertTrue(engine.last_metrics.get("token_events", 0) >= 1)
        finally:
            engine.stop()
