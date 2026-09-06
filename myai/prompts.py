"""Prompt and tool protocol definitions for the local ReAct agent."""
import json


TOOL_SCHEMAS = {
    "inspect_system": {"type": "object", "properties": {"process_limit": {"type": "integer"}}},
    "execute_command": {
        "type": "object",
        "properties": {
            "command": {"type": ["string", "array"]},
            "timeout": {"type": "number"},
        },
        "required": ["command"],
    },
    "navigate": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]},
    "take_screenshot": {
        "type": "object",
        "properties": {"filepath": {"type": "string"}},
        "required": ["filepath"],
    },
    "click_and_type": {
        "type": "object",
        "properties": {"selector": {"type": "string"}, "text": {"type": "string"}},
        "required": ["selector", "text"],
    },
}


AGENT_SYSTEM_PROMPT = (
    "You are MyAi Agent. Work toward the user's goal using a bounded ReAct loop. "
    "Break complex goals into small sub-goals and never invent observations. "
    "Available tools and argument schemas are:\n"
    f"{json.dumps(TOOL_SCHEMAS, sort_keys=True)}\n"
    "For every step, emit exactly these lines and no markdown:\n"
    "Thought: <concise reasoning about the current state>\n"
    'Action: {"tool": "<tool_name>", "args": {<arguments>}}\n'
    "Use only the listed tool names. After the goal is complete, emit exactly:\n"
    "Final Answer: <response to user>\n"
    "If a tool fails or times out, use its error observation to self-correct."
)


def agent_system_prompt():
    """Return the prompt through the historical callable API."""
    return AGENT_SYSTEM_PROMPT
