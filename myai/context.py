"""Conservative conversation context budgeting.

Token counts are estimated as UTF-8 bytes/4. That is a planning heuristic, not
a tokenizer, and it is labeled as such in API responses.
"""
from __future__ import annotations

CHAR_PER_TOKEN = 4
CONTEXT_CHOICES = (2048, 4096, 8192, 16384)


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, (len(text.encode("utf-8")) + CHAR_PER_TOKEN - 1) // CHAR_PER_TOKEN)


def budget_messages(messages, context_tokens, reserve_tokens=1024):
    """Keep the system prompt and newest turns that fit in ``context_tokens``.

    The latest user message is never dropped. Older complete turns are removed
    from the front (after any system message) until the estimate fits.
    """
    if type(context_tokens) is not int or context_tokens not in CONTEXT_CHOICES:
        raise ValueError("Unsupported context size")
    if type(reserve_tokens) is not int or reserve_tokens < 16:
        raise ValueError("Reserve tokens must be a positive integer")
    budget = context_tokens - reserve_tokens
    if budget < 64:
        raise ValueError("Context budget is too small for a reply")
    messages = [dict(m) for m in messages]
    kept = list(messages)
    dropped = 0

    def total(items):
        return sum(estimate_tokens(m.get("content", "")) + 8 for m in items)

    while len(kept) > 1 and total(kept) > budget:
        index = 1 if kept and kept[0].get("role") == "system" else 0
        # Never drop the final user turn.
        if index >= len(kept) - 1:
            break
        if kept[-1].get("role") == "user" and index == len(kept) - 1:
            break
        kept.pop(index)
        dropped += 1
        # If we dropped an assistant that now leaves two users in a row at the
        # front of the history, continue; llama.cpp accepts that more readily
        # than overflowing the window.
    fitted = total(kept) <= budget
    return {
        "messages": kept,
        "dropped": dropped,
        "kept": len(kept),
        "estimated_tokens": total(kept),
        "budget_tokens": budget,
        "reserve_tokens": reserve_tokens,
        "estimator": "utf8_bytes/4",
        "fitted": fitted,
    }
