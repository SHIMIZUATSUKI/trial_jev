import os
import sys
import types
import unittest
from unittest.mock import patch

from src.urgency_benchmark import run_gpt_decisions


class FakeDecisions:
    def __init__(self):
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        prob = types.SimpleNamespace
        return types.SimpleNamespace(
            answers=[
                types.SimpleNamespace(
                    type="choice",
                    name="urgency",
                    choice="medium",
                    confidence=0.6,
                    probabilities=[prob(value="high", probability=0.3), prob(value="medium", probability=0.6)],
                )
            ]
        )


class FakeOpenAIClient:
    instances = []

    def __init__(self):
        self.decisions = FakeDecisions()
        FakeOpenAIClient.instances.append(self)


class TestGptDecisions(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-key"}, clear=False)
    def test_run_gpt_decisions_returns_choice_and_excludes_warmup(self):
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAIClient
        FakeOpenAIClient.instances = []

        with patch.dict(sys.modules, {"openai": fake_openai}):
            preds, times, extra = run_gpt_decisions(["a", "b"])

        self.assertEqual(preds, ["medium", "medium"])
        self.assertEqual(len(times), 2)  # ウォームアップは計測に含めない
        self.assertEqual(len(FakeOpenAIClient.instances), 1)
        calls = FakeOpenAIClient.instances[0].decisions.calls
        self.assertEqual(len(calls), 3)
        q = calls[0]["questions"][0]
        self.assertEqual(q["type"], "choice")
        self.assertEqual([c["value"] for c in q["choices"]], ["high", "medium", "low"])


if __name__ == "__main__":
    unittest.main()
