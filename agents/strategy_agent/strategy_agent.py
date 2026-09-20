import json
import os
import re
from functools import lru_cache

from dotenv import load_dotenv
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import PromptTemplate

from .llm import build_llm
from .prompt import STRATEGY_SYSTEM_PROMPT, AGENCY_SERVICES
from .reflection import llm_critic, llm_reviser, reflect_and_revise
from .tools import web_search, get_upcoming_events
from database.database import SessionLocal
from database.repository import save_strategy_result

load_dotenv()


class StrategyValidationError(ValueError):
    """The strategy still breaks the output contract after self-reflection; it must not be saved."""


# =========================================================
# TOOLS
# =========================================================

tools = [
    get_upcoming_events,
    web_search,
]


# =========================================================
# REACT PROMPT
# =========================================================

react_template = """
Answer the following task using the available tools when required.

You have access to the following tools:

{tools}

Tool names:

{tool_names}


==================================================
TOOL EXECUTION POLICY
==================================================

get_upcoming_events is required exactly once for every 30-day strategy.

Use the strategy start date provided in the task.

Call the tool with:

Action: get_upcoming_events
Action Input: <strategy_start_date>

After receiving the calendar observation:

- Evaluate each returned event for strategic relevance.
- Use an event only when it supports the restaurant's verified
  marketing needs.
- Do not force an irrelevant event into the strategy.
- Do not call get_upcoming_events more than once.


web_search is optional.

Use web_search only when current external information would materially
improve the strategy.

Do not use web_search to research the restaurant again.

If web_search is not necessary, proceed to the Final Answer after
considering the calendar result.


==================================================
REACT FORMAT
==================================================

When a tool is required, use:

Thought: determine the next required step

Action: one of [{tool_names}]

Action Input: the input required by the selected tool


After receiving the Observation, determine whether another tool is
needed.

Repeat the tool workflow only when another tool is genuinely necessary.


When no additional tool is needed, use:

Thought: I now have enough information to produce the strategy.

Final Answer:
[valid JSON]


==================================================
IMPORTANT
==================================================

- Never produce the Final Answer before get_upcoming_events has been
  called.
- Never call get_upcoming_events more than once.
- web_search remains optional.
- Never return raw JSON without the literal text "Final Answer:".
- The Final Answer must follow the JSON structure specified in the task.
- Do not expose internal reasoning in the Final Answer.


Begin!

Question:
{input}

Thought:
{agent_scratchpad}
"""


react_prompt = PromptTemplate.from_template(
    react_template
)


# =========================================================
# STRATEGY AGENT
# =========================================================

@lru_cache(maxsize=1)
def get_llm():
    """Chat model from STRATEGY_LLM (see llm.py); created on first use so importing needs no API key."""
    return build_llm()


@lru_cache(maxsize=1)
def get_executor():
    agent = create_react_agent(
        llm=get_llm(),
        tools=tools,
        prompt=react_prompt,
        stop_sequence=False
    )

    return AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=os.getenv("STRATEGY_VERBOSE", "").lower() in {"1", "true", "yes"},
        max_iterations=5,
        handle_parsing_errors=(
            "Invalid ReAct format. "
            "If get_upcoming_events has already returned an Observation, "
            "do not call it again. "
            "Do not return raw JSON directly. "
            "Return exactly in this format: "
            "Thought: I now have enough information to produce the strategy. "
            "Final Answer: "
            "{valid JSON}"
        )
    )


def _parse_json(text: str) -> dict:
    """The model's Final Answer as a dict, tolerating markdown fences or a stray sentence around it."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end <= start:
        raise StrategyValidationError("The Strategy Agent did not return a JSON object.")
    try:
        return json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError as error:
        raise StrategyValidationError(f"The Strategy Agent returned invalid JSON: {error}") from error


# =========================================================
# GENERATE STRATEGY
# =========================================================

def _interest_section(interest: dict | None) -> str:
    """The prompt section telling the agent the restaurant confirmed interest (empty when unknown)."""
    if not interest:
        return ""
    return f"""

==================================================
CLIENT INTEREST (verified)
==================================================

The restaurant confirmed interest in Rawaj by clicking "Interested" in the
outreach email on {interest.get("interested_on")}.

Customer request: {interest.get("customer_request")}

This is the restaurant's complimentary trial strategy, so make it concrete
and immediately actionable from Day 1. The confirmation is not evidence of
any restaurant need: ground every recommendation in the Qualification Agent
output and do not invent needs, offers or preferences from it.
"""


def generate_strategy_with_reflection(
    qualification_data: dict,
    strategy_start_date: str,
    interest: dict | None = None,
) -> dict:
    """Draft with the ReAct agent, then self-reflect. Returns strategy, draft, rounds, errors, warnings."""

    qualification_text = json.dumps(
        qualification_data,
        indent=2,
        ensure_ascii=False
    )

    strategy_instructions = STRATEGY_SYSTEM_PROMPT.replace(
        "{agency_services}",
        AGENCY_SERVICES
    )

    result = get_executor().invoke(
        {
            "input": f"""
{strategy_instructions}


==================================================
STRATEGY PERIOD
==================================================

Strategy start date: {strategy_start_date}
{_interest_section(interest)}

==================================================
QUALIFICATION AGENT OUTPUT
==================================================

{qualification_text}


==================================================
TASK
==================================================

Generate a 30-day marketing strategy based on the verified
Qualification Agent output.

Use the provided strategy start date as Day 1 of the 30-day strategy.

Only recommend services from the provided AGENCY SERVICES.

Use get_upcoming_events to check the Saudi calendar for the
30-day strategy period.

Use web_search only if current external information would materially
improve the strategy.

Do not invent restaurant facts, marketing gaps, offers, products,
metrics, or agency services.
"""
        }
    )

    draft = _parse_json(result["output"])

    llm = get_llm()
    return reflect_and_revise(
        draft,
        qualification_data,
        strategy_start_date,
        critic=llm_critic(llm),
        reviser=llm_reviser(llm),
    )


def generate_strategy(
    qualification_data: dict,
    strategy_start_date: str,
    interest: dict | None = None,
):
    """The final, self-reflected strategy; raises StrategyValidationError if it still breaks the contract."""
    outcome = generate_strategy_with_reflection(qualification_data, strategy_start_date, interest)

    if outcome["errors"]:
        raise StrategyValidationError(
            "The strategy failed validation after self-reflection: " + "; ".join(outcome["errors"])
        )

    return outcome["strategy"]


# =========================================================
# HANDOFF ENTRY POINT
# =========================================================

def generate_strategy_from_handoff(strategy_request):

    if hasattr(strategy_request, "model_dump"):
        strategy_request = strategy_request.model_dump(mode="json")

    qualification_data = strategy_request["qualification_context"]
    strategy_start_date = strategy_request["strategy_start_date"]

    if not strategy_start_date:
        raise ValueError(
            "strategy_start_date is missing from StrategyRequestHandoff."
        )

    # A strategy is only ever built for a restaurant that verifiably clicked "Interested".
    if not strategy_request.get("interest_event_id"):
        raise ValueError(
            "interest_event_id is missing from StrategyRequestHandoff: "
            "a strategy needs a verified Interested event."
        )

    return generate_strategy(
        qualification_data=qualification_data,
        strategy_start_date=strategy_start_date,
        interest={
            "interested_on": strategy_start_date,
            "customer_request": strategy_request.get("customer_request"),
        },
    )

def generate_and_save_strategy_from_handoff(strategy_request):

    if hasattr(strategy_request, "model_dump"):
        request_data = strategy_request.model_dump(mode="json")
    else:
        request_data = strategy_request

    # Generate strategy
    strategy_data = generate_strategy_from_handoff(request_data)
    # Day numbers count from this date; the UI needs it to place each day on the calendar.
    strategy_data["strategy_start_date"] = request_data["strategy_start_date"]
    # Keep which request and which Interested click this strategy answers.
    strategy_data["strategy_request_id"] = request_data.get("strategy_request_id")
    strategy_data["interest_event_id"] = request_data["interest_event_id"]

    # Open database session
    db = SessionLocal()

    try:
        saved_strategy = save_strategy_result(
            db=db,
            restaurant_id=int(request_data["restaurant_id"]),
            qualification_run_id=(
                int(request_data["qualification_run_id"])
                if request_data.get("qualification_run_id") is not None
                else None
            ),
            result=strategy_data,
        )

        return {
            "strategy_id": saved_strategy.id,
            "strategy_data": strategy_data,
        }

    finally:
        db.close()