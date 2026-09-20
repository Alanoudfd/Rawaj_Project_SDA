"""Self-Reflection for the Strategy Agent: draft -> critique -> revise, as visible, checkable steps.

The draft comes from the ReAct agent. Each round runs the deterministic guardrails plus an LLM
critique against the prompt's SELF-REFLECTION criteria; if anything is found the strategy is
revised and checked again. Every step is a traced LangSmith run, and the draft is kept so an
evaluation can measure whether reflection actually improved the result.
"""

import json
import logging

from langsmith import traceable
from pydantic import BaseModel, Field

from .guardrails import check_strategy
from .schemas import StrategyOutput

logger = logging.getLogger(__name__)

MAX_ROUNDS = 2

CRITIQUE_PROMPT = """You are reviewing a draft 30-day marketing strategy for a restaurant, written from a
Qualification Agent report. Judge it against these criteria and list only real problems.

1. Evidence grounding - every restaurant-specific claim is supported by the qualification report; no
   invented facts, metrics, offers or products.
2. Gap selection - the highest-impact High/Moderate gaps are prioritised and supported by evidence.
3. Target quality - at most 3 targets that address those gaps, with no unsupported performance promises.
4. Service relevance - each recommended service directly addresses a verified need; none unnecessary.
5. Plan quality - one focus and one concise strategic action per day; logical progression; no needless
   repetition; rest/monitoring days are justified; event preparation and follow-up sit around the event;
   no detailed captions, scripts or creative briefs; day 30 does not plan the next month.
6. Events - an occasion is used only if it is strategically relevant; a tentative date is not presented
   as confirmed.

Automated checks already found the issues listed under "Automated findings". Do not repeat them; add
only problems that need judgement. Set passed=true only when there is nothing left to fix.

QUALIFICATION REPORT
{qualification}

AUTOMATED FINDINGS
{automated}

DRAFT STRATEGY
{strategy}
"""

REVISE_PROMPT = """Revise this 30-day restaurant marketing strategy so that it fixes every issue listed
below. Change only what the issues require. Keep exactly 30 days (1-30, each once), at most 3 targets, only
services from the agency services, and ground every claim in the qualification report. Do not invent
restaurant facts, metrics or offers. Return the complete corrected strategy.

ISSUES TO FIX
{issues}

QUALIFICATION REPORT
{qualification}

CURRENT STRATEGY
{strategy}
"""


class Critique(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


def _dump(value) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False)


def llm_critic(llm):
    structured = llm.with_structured_output(Critique)

    @traceable(name="strategy_critique", run_type="chain")
    def critic(strategy: dict, qualification: dict | None, check: dict) -> Critique:
        automated = [*check["errors"], *check["warnings"]]
        return structured.invoke(CRITIQUE_PROMPT.format(
            qualification=_dump(qualification), strategy=_dump(strategy),
            automated="\n".join(f"- {item}" for item in automated) or "none",
        ))

    return critic


def llm_reviser(llm):
    structured = llm.with_structured_output(StrategyOutput)

    @traceable(name="strategy_revision", run_type="chain")
    def reviser(strategy: dict, qualification: dict | None, issues: list[str]) -> dict:
        revised = structured.invoke(REVISE_PROMPT.format(
            issues="\n".join(f"- {item}" for item in issues),
            qualification=_dump(qualification), strategy=_dump(strategy),
        ))
        return revised.model_dump()

    return reviser


@traceable(name="strategy_self_reflection", run_type="chain")
def reflect_and_revise(
    draft: dict,
    qualification: dict | None,
    start_date: str | None,
    *,
    critic,
    reviser,
    max_rounds: int = MAX_ROUNDS,
) -> dict:
    """Returns {"strategy", "draft", "rounds", "errors", "warnings"} for the final strategy."""
    current, rounds = draft, []
    for number in range(1, max_rounds + 1):
        check = check_strategy(current, qualification, start_date)
        critique = critic(current, qualification, check)
        issues = [*check["errors"], *check["warnings"], *critique.issues]
        rounds.append({"round": number, "issues": issues, "passed": critique.passed and not issues})
        if not issues:
            break
        logger.info("Strategy reflection round %s found %s issue(s); revising.", number, len(issues))
        current = reviser(current, qualification, issues)
    final = check_strategy(current, qualification, start_date)
    return {"strategy": current, "draft": draft, "rounds": rounds, **final}
