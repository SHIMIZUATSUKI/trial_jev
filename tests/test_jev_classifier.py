import os
import sys
import types
import unittest
from unittest.mock import patch

from src.urgency_benchmark import classify_jev, run_jev


class FakeChoiceResult:
    def __init__(self, choice, probabilities, confidence):
        self.choice = choice
        self.probabilities = probabilities
        self.confidence = confidence


class FakeTypeSafeClient:
    instances = 0

    def __init__(self):
        FakeTypeSafeClient.instances += 1
        self.calls = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def system_one(self, model, state, questions):
        self.calls += 1
        return type(
            "FakeResponse",
            (),
            {
                "answers": {
                    "urgency": FakeChoiceResult(
                        choice="high",
                        probabilities={"high": 0.7, "medium": 0.2, "low": 0.1},
                        confidence=0.8,
                    )
                }
            },
        )()


class TestJevClassifier(unittest.TestCase):
    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "dummy-key"}, clear=False)
    def test_classify_jev_returns_high_from_choice_result(self):
        fake_sdk = types.ModuleType("typesafe_sdk")
        fake_sdk.Choice = lambda **kwargs: kwargs
        fake_sdk.TypeSafeClient = FakeTypeSafeClient
        with patch.dict(sys.modules, {"typesafe_sdk": fake_sdk}):
            result = classify_jev("本番環境の障害が発生し、すぐ対応が必要です")
        self.assertEqual(result, "high")

    @patch.dict(os.environ, {"TYPESAFE_API_KEY": "dummy-key"}, clear=False)
    def test_run_jev_reuses_one_client_and_excludes_warmup(self):
        fake_sdk = types.ModuleType("typesafe_sdk")
        fake_sdk.Choice = lambda **kwargs: kwargs
        fake_sdk.TypeSafeClient = FakeTypeSafeClient
        FakeTypeSafeClient.instances = 0
        with patch.dict(sys.modules, {"typesafe_sdk": fake_sdk}):
            preds, times, extra = run_jev(["a", "b", "c"])
        self.assertEqual(FakeTypeSafeClient.instances, 1)
        self.assertEqual(preds, ["high"] * 3)
        self.assertEqual(len(times), 3)  # ウォームアップは計測に含めない


if __name__ == "__main__":
    unittest.main()
