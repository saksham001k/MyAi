import unittest

from myai.agent import AutonomousAgent


class FakeEngine:
    def __init__(self, responses, results=None):
        self.responses = iter(responses)
        self.results = results or {}
        self.calls = []

    def stream(self, _messages, _temperature, max_tokens=1024):
        del max_tokens
        return iter(next(self.responses))

    def call_tool(self, name, **args):
        self.calls.append((name, args))
        result = self.results.get(name)
        if isinstance(result, Exception):
            raise result
        return result if result is not None else {"ok": True}


class AgentTests(unittest.TestCase):
    def test_parser_extracts_thought_action_and_final(self):
        action = AutonomousAgent.parse_response(
            'Thought: inspect the host\nAction: {"tool":"inspect_system","args":{}}'
        )
        self.assertEqual(action["thought"], "inspect the host")
        self.assertEqual(action["tool"], "inspect_system")
        final = AutonomousAgent.parse_response("Final Answer: done")
        self.assertEqual(final, {"type": "final", "content": "done"})

    def test_multi_step_loop_and_termination(self):
        engine = FakeEngine([
            'Thought: inspect\nAction: {"tool":"inspect_system","args":{}}',
            "Final Answer: The check is complete.",
        ])
        events = []
        result = AutonomousAgent(engine).run("Check my computer.", events.append)
        self.assertEqual(engine.calls, [("inspect_system", {})])
        self.assertEqual(result["answer"], "The check is complete.")
        self.assertEqual([event["type"] for event in events],
                         ["thought", "action", "observation", "final"])

    def test_error_recovery_and_max_iterations(self):
        engine = FakeEngine([
            'Thought: try command\nAction: {"tool":"execute_command","args":{"command":"bad"}}',
            "Final Answer: The command failed and I stopped safely.",
        ], {"execute_command": RuntimeError("non-zero exit")})
        result = AutonomousAgent(engine).run("Run a command.")
        self.assertEqual(result["status"], "complete")
        self.assertFalse(result["observations"][0]["ok"])

        looping = FakeEngine([
            'Thought: continue\nAction: {"tool":"inspect_system","args":{}}'
        ] * 2)
        limited = AutonomousAgent(looping, max_iterations=2).run("Repeat.")
        self.assertEqual(limited["status"], "limited")
        self.assertEqual(limited["iterations"], 2)


if __name__ == "__main__":
    unittest.main()
