import unittest

from myai.context import budget_messages, estimate_tokens


class ContextBudgetTests(unittest.TestCase):
    def test_drops_oldest_turns_but_keeps_latest_user(self):
        messages = [{"role": "system", "content": "sys"}]
        for i in range(40):
            messages.append({"role": "user", "content": ("question " + str(i) + " ") * 80})
            messages.append({"role": "assistant", "content": ("answer " + str(i) + " ") * 80})
        messages.append({"role": "user", "content": "final question"})
        result = budget_messages(messages, 2048, reserve_tokens=256)
        self.assertGreater(result["dropped"], 0)
        self.assertEqual(result["messages"][0]["role"], "system")
        self.assertEqual(result["messages"][-1]["content"], "final question")
        self.assertTrue(result["fitted"])
        self.assertEqual(result["estimator"], "utf8_bytes/4")

    def test_estimate_is_bytes_over_four(self):
        self.assertEqual(estimate_tokens("abcd"), 1)
        self.assertGreaterEqual(estimate_tokens("hello world"), 2)


if __name__ == "__main__":
    unittest.main()
