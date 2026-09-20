"""Offline tests for the Strategy Agent guardrails, self-reflection loop and model selection.

No model or network is used; the critic/reviser and the ReAct executor are replaced by fakes.
Run with: python -m unittest tests.test_strategy_guardrails -v
"""

import copy
import unittest
from unittest.mock import patch

with patch("dotenv.load_dotenv", return_value=False):
    from agents.strategy_agent import strategy_agent
    from agents.strategy_agent.guardrails import allowed_services, check_strategy
    from agents.strategy_agent.llm import build_llm, parse_spec
    from agents.strategy_agent.reflection import Critique, reflect_and_revise

QUALIFICATION = {
    "marketing_gaps": [
        {"gap": "Prolonged Posting Inactivity", "severity": "High", "priority": 1,
         "evidence": ["0 posts in 30 days.", "Menu visibility 10.71%."], "recommendation_focus": "Consistency"},
        {"gap": "Narrow Content Mix", "severity": "Moderate", "priority": 2, "evidence": [], "recommendation_focus": "Mix"},
    ]
}
START = "2026-09-20"  # Saudi National Day (2026-09-23) is day 4


def valid_strategy():
    return {
        "restaurant": "3Brews",
        "primary_marketing_gaps": [
            {"gap": "Prolonged Posting Inactivity", "severity": "High", "highlight": "10.71%",
             "highlight_label": "menu visibility", "key_point": "No recent posts."},
        ],
        "thirty_day_target": ["Restore a posting rhythm", "Show the menu"],
        "recommended_services": [{"service": "Social Media Strategy", "why_this_service_fits": "Fixes cadence."}],
        "thirty_day_plan": [
            {"day": day, "focus": f"Focus {day}", "action": f"Action {day}."} for day in range(1, 31)
        ],
        "external_trend_support": [],
    }


class GuardrailTests(unittest.TestCase):
    def check(self, data, **kwargs):
        return check_strategy(data, QUALIFICATION, START, **kwargs)

    def test_agency_services_are_parsed_from_the_prompt(self):
        self.assertEqual(allowed_services(), {
            "Social Media Strategy", "Content Strategy", "Campaign Strategy",
            "Engagement Strategy", "Brand Communication Strategy", "Paid Advertising Strategy",
        })

    def test_valid_strategy_has_no_findings(self):
        self.assertEqual(self.check(valid_strategy()), {"errors": [], "warnings": []})

    def test_contract_violations_are_errors(self):
        data = valid_strategy()
        data["thirty_day_plan"].pop()
        data["thirty_day_plan"][0]["day"] = 2
        self.assertTrue(any("plan must contain days 1-30" in e for e in self.check(data)["errors"]))

        data = valid_strategy()
        data["recommended_services"][0]["service"] = "Influencer Marketing"
        self.assertTrue(any("not one of the agency services" in e for e in self.check(data)["errors"]))

        data = valid_strategy()
        data["thirty_day_target"] = ["a", "b", "c", "d"]
        self.assertTrue(any("thirty_day_target" in e for e in self.check(data)["errors"]))

        data = valid_strategy()
        data["expected_marketing_objective"] = "not allowed"
        self.assertTrue(any("expected_marketing_objective" in e for e in self.check(data)["errors"]))

        data = valid_strategy()
        data["primary_marketing_gaps"][0]["severity"] = "Low"
        self.assertTrue(any("severity" in e for e in self.check(data)["errors"]))

    def test_grounding_problems_are_warnings(self):
        data = valid_strategy()
        data["primary_marketing_gaps"] = [
            {"gap": "Slow Website", "severity": "High", "highlight": "99%", "key_point": "x"},
            {"gap": "Narrow Content Mix", "severity": "High", "highlight": None, "key_point": "y"},
        ]
        result = self.check(data)
        self.assertEqual(result["errors"], [])
        joined = " | ".join(result["warnings"])
        self.assertIn("'Slow Website' is not in the Qualification Agent output", joined)
        self.assertIn("is Moderate in qualification but High here", joined)
        self.assertIn("highlight '99%'", joined)

    def test_event_mentions_must_sit_near_the_event(self):
        data = valid_strategy()
        data["thirty_day_plan"][3]["focus"] = "Saudi National Day campaign"      # day 4: on the event
        self.assertEqual(self.check(data)["warnings"], [])
        data["thirty_day_plan"][24]["action"] = "Post about Saudi National Day"   # day 25: 3 weeks late
        self.assertTrue(any("Saudi National Day" in w and "[25]" in w for w in self.check(data)["warnings"]))

    def test_tentative_event_is_not_presented_as_confirmed(self):
        data = valid_strategy()
        data["thirty_day_plan"][0]["action"] = "Confirmed Ramadan preparation"
        result = check_strategy(data, QUALIFICATION, "2027-02-01")  # Ramadan (tentative) starts 2027-02-08
        self.assertTrue(any("tentative event 'Ramadan'" in w for w in result["warnings"]))


class ReflectionTests(unittest.TestCase):
    def test_a_clean_draft_passes_without_revision(self):
        calls = []
        outcome = reflect_and_revise(
            valid_strategy(), QUALIFICATION, START,
            critic=lambda s, q, c: Critique(passed=True),
            reviser=lambda *a: calls.append(a),
        )
        self.assertEqual(calls, [])
        self.assertEqual(len(outcome["rounds"]), 1)
        self.assertEqual(outcome["errors"], [])

    def test_the_reviser_receives_every_issue_and_its_fix_is_rechecked(self):
        broken = valid_strategy()
        broken["thirty_day_plan"].pop()
        seen = []

        def reviser(strategy, qualification, issues):
            seen.append(issues)
            return valid_strategy()

        critiques = iter([Critique(passed=False, issues=["Day 12 repeats day 11."]), Critique(passed=True)])
        outcome = reflect_and_revise(
            broken, QUALIFICATION, START,
            critic=lambda s, q, c: next(critiques),
            reviser=reviser,
        )
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(outcome["rounds"]), 2)
        self.assertTrue(any("plan must contain days 1-30" in i for i in seen[0]))
        self.assertIn("Day 12 repeats day 11.", seen[0])
        self.assertEqual(outcome["errors"], [])
        self.assertEqual(outcome["draft"], broken)
        self.assertEqual(len(outcome["strategy"]["thirty_day_plan"]), 30)

    def test_rounds_are_capped_and_remaining_errors_are_reported(self):
        broken = valid_strategy()
        broken["thirty_day_plan"].pop()
        outcome = reflect_and_revise(
            broken, QUALIFICATION, START,
            critic=lambda s, q, c: Critique(passed=False),
            reviser=lambda s, q, i: copy.deepcopy(broken),
            max_rounds=2,
        )
        self.assertEqual(len(outcome["rounds"]), 2)
        self.assertTrue(outcome["errors"])


class GenerateStrategyTests(unittest.TestCase):
    class FakeExecutor:
        def __init__(self, output):
            self.output = output

        def invoke(self, payload):
            return {"output": self.output}

    def run_generate(self, output, critique=Critique(passed=True)):
        with patch.object(strategy_agent, "get_executor", return_value=self.FakeExecutor(output)), \
                patch.object(strategy_agent, "get_llm", return_value=object()), \
                patch.object(strategy_agent, "llm_critic", return_value=lambda s, q, c: critique), \
                patch.object(strategy_agent, "llm_reviser", return_value=lambda s, q, i: valid_strategy()):
            return strategy_agent.generate_strategy(QUALIFICATION, START)

    def test_fenced_json_is_accepted(self):
        import json
        result = self.run_generate("```json\n" + json.dumps(valid_strategy()) + "\n```")
        self.assertEqual(len(result["thirty_day_plan"]), 30)

    def test_a_broken_draft_is_repaired_by_reflection(self):
        import json
        broken = valid_strategy()
        broken["thirty_day_plan"].pop()
        result = self.run_generate(json.dumps(broken), critique=Critique(passed=False))
        self.assertEqual(len(result["thirty_day_plan"]), 30)

    def test_output_that_is_not_json_is_rejected(self):
        with self.assertRaises(strategy_agent.StrategyValidationError):
            self.run_generate("I could not build a strategy.")


class ModelSelectionTests(unittest.TestCase):
    def test_spec_parsing(self):
        self.assertEqual(parse_spec(" OpenAI : gpt-5.6 "), ("openai", "gpt-5.6"))
        with self.assertRaises(ValueError):
            parse_spec("openai")
        with self.assertRaises(ValueError):
            build_llm("anthropic:claude-sonnet-5")  # only OpenAI is supported


if __name__ == "__main__":
    unittest.main()
