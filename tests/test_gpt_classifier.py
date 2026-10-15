import json
import os
import sys
import types
import unittest
from unittest.mock import patch

from src.urgency_benchmark import run_gpt


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeChatCompletions:
    def __init__(self):
        pass

    def create(self, **kwargs):
        return types.SimpleNamespace(
            choices=[FakeChoice(json.dumps({"urgency": "high"}, ensure_ascii=False))]
        )


class FakeOpenAIClient:
    def __init__(self):
        self.chat = types.SimpleNamespace(completions=FakeChatCompletions())


class TestGptClassifier(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-key"}, clear=False)
    def test_run_gpt_returns_high_from_json_response(self):
        fake_openai = types.ModuleType("openai")
        fake_openai.OpenAI = FakeOpenAIClient

        with patch.dict(sys.modules, {"openai": fake_openai}):
            preds, times, extra = run_gpt(["本番環境で障害が起きているため、今すぐ対応が必要です"])

        self.assertEqual(preds, ["high"])
        self.assertEqual(len(times), 1)
        self.assertEqual(extra, {})


if __name__ == "__main__":
    unittest.main()
