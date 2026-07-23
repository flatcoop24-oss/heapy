import unittest

from guidance_api.condition_engine import evaluate_condition


class PolicyConditionEngineTest(unittest.TestCase):
    def test_nested_all_any_and_missing(self):
        facts = {
            "request": {"clinical": True},
            "context": {"age": 40},
        }
        self.assertTrue(
            evaluate_condition(
                {
                    "all": [
                        {"field": "request.clinical", "operator": "eq", "value": True},
                        {
                            "any": [
                                {"field": "context.age", "operator": "eq", "value": 40},
                                {"field": "context.age", "operator": "eq", "value": 50},
                            ]
                        },
                    ]
                },
                facts,
            )
        )
        self.assertTrue(evaluate_condition({"missing_any": ["context.location"]}, facts))

    def test_unknown_operator_fails_closed(self):
        self.assertFalse(
            evaluate_condition(
                {"field": "request.clinical", "operator": "approximately", "value": True},
                {"request": {"clinical": True}},
            )
        )


if __name__ == "__main__":
    unittest.main()
