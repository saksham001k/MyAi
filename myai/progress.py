"""Shared progress-event protocol for all MyAi operational modes."""


def progress_event(mode, stage, percentage, details=""):
    """Build a bounded, frontend-safe progress event."""
    if not isinstance(mode, str) or not mode:
        raise ValueError("Progress mode is required")
    if not isinstance(stage, str) or not stage:
        raise ValueError("Progress stage is required")
    if type(percentage) not in (int, float):
        raise TypeError("Progress percentage must be numeric")
    return {
        "type": "progress",
        "mode": mode,
        "stage": stage,
        "percentage": max(0, min(100, round(percentage))),
        "details": details if isinstance(details, str) else str(details),
    }
