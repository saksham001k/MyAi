"""Honest generation-speed measurement.

Values come from llama.cpp ``timings`` when present. Otherwise the client
records wall-clock time to the first content event and content-event rate.
Content events are not tokenizer tokens; the API labels the source.
"""
from __future__ import annotations

import time


def empty_metrics():
    return {
        "time_to_first_token_ms": None,
        "tokens_per_second": None,
        "prompt_ms": None,
        "predicted_n": None,
        "token_events": 0,
        "source": None,
        "note": "No measurement yet. Load a model and send a prompt or run calibration.",
    }


def parse_llama_timings(event):
    timings = event.get("timings") if isinstance(event, dict) else None
    if not isinstance(timings, dict):
        return None
    predicted = timings.get("predicted_per_second")
    prompt_ms = timings.get("prompt_ms")
    predicted_n = timings.get("predicted_n")
    result = {
        "prompt_ms": prompt_ms if isinstance(prompt_ms, (int, float)) else None,
        "predicted_n": predicted_n if isinstance(predicted_n, (int, float)) else None,
        "tokens_per_second": predicted if isinstance(predicted, (int, float)) else None,
        "source": "llama.cpp timings",
    }
    if result["prompt_ms"] is not None:
        result["time_to_first_token_ms"] = round(result["prompt_ms"])
    return result


class StreamMeter:
    """Wrap a token iterator and collect wall-clock plus optional engine timings."""

    def __init__(self):
        self.metrics = empty_metrics()
        self.metrics["note"] = None

    def watch(self, tokens, llama_event=None):
        started = time.monotonic()
        first = None
        count = 0
        try:
            for token in tokens:
                if first is None:
                    first = time.monotonic()
                count += 1
                extra = llama_event() if llama_event else None
                parsed = parse_llama_timings(extra) if extra else None
                if parsed:
                    self.metrics.update({k: v for k, v in parsed.items() if v is not None})
                yield token
        finally:
            ended = time.monotonic()
            self.metrics["token_events"] = count
            if first is not None and self.metrics.get("time_to_first_token_ms") is None:
                self.metrics["time_to_first_token_ms"] = round((first - started) * 1000)
                self.metrics["source"] = self.metrics.get("source") or "wall-clock content events"
                self.metrics["note"] = (
                    "time_to_first_token_ms is wall-clock until the first streamed "
                    "content event. tokens_per_second is omitted unless llama.cpp "
                    "timings are present; content events are not tokenizer tokens."
                )
            elif self.metrics.get("source") == "llama.cpp timings":
                self.metrics["note"] = (
                    "tokens_per_second and prompt_ms come from llama.cpp timings. "
                    "They are measurements from this run, not a product claim."
                )
            if (
                self.metrics.get("tokens_per_second") is None
                and first is not None
                and ended > first
                and count > 1
            ):
                # Keep a clearly labeled fallback so the UI can show *something*
                # without pretending these are tokenizer tokens.
                self.metrics["content_events_per_second"] = round(count / (ended - first), 2)
            if first is None:
                self.metrics["note"] = "The engine produced no content events."
