"""Callable local tools available to the MyAi agent."""

from .system_control import execute_command, inspect_system
from .browser_control import click_and_type, navigate, take_screenshot

__all__ = [
    "click_and_type",
    "execute_command",
    "inspect_system",
    "navigate",
    "take_screenshot",
]
