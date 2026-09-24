import json
import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain_classic.agents import create_react_agent, AgentExecutor
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from database.database import SessionLocal
from database.repository import save_strategy_result
from .reflection_prompt import SELF_REFLECTION_PROMPT
from .prompt import STRATEGY_SYSTEM_PROMPT, AGENCY_SERVICES
from .tools import web_search, get_upcoming_events
from .guardrails import check_strategy

load_dotenv()


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
    """The Strategy model: OPENAI_MODEL from .env, the same model every agent uses (default gpt-5.6-luna).
    Created on first use, so importing this file needs no API key."""
    return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), use_responses_api=True)


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


# =========================================================
# REFLECTION (Shaimaa)
# =========================================================
def reflect_strategy(
    qualification_data: dict,
    initial_strategy: dict,
    strategy_start_date: str,
) -> dict:
    """
    Perform a second LLM call using the same Strategy Agent model
    to review and correct the Initial Strategy Result.
    """

    qualification_text = json.dumps(
        qualification_data,
        indent=2,
        ensure_ascii=False,
    )

    initial_strategy_text = json.dumps(
        initial_strategy,
        indent=2,
        ensure_ascii=False,
    )

    reflection_input = f"""
{SELF_REFLECTION_PROMPT}

==================================================
STRATEGY START DATE
==================================================

{strategy_start_date}

==================================================
ALLOWED AGENCY SERVICES
==================================================

{AGENCY_SERVICES}

==================================================
QUALIFICATION AGENT OUTPUT
==================================================

{qualification_text}

==================================================
INITIAL STRATEGY RESULT
==================================================

{initial_strategy_text}

==================================================
TASK
==================================================

Perform the self-reflection now.

Review your Initial Strategy Result using all reflection questions above.

Return only the required JSON containing:

- passed
- issues
- corrected_strategy
"""

    response = get_llm().invoke(
        reflection_input,
        config={
            "run_name": "Strategy Self Reflection"
        },
    )

    reflection_data = json.loads(response.text)

    if "corrected_strategy" not in reflection_data:
        raise ValueError(
            "Self-reflection output is missing corrected_strategy."
        )

    return reflection_data


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


# =========================================================
# GENERATE STRATEGY
# =========================================================

def generate_strategy(
    qualification_data: dict,
    strategy_start_date: str,
    return_evaluation_data: bool = False,
    interest: dict | None = None,
):

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
    },
    config={
        "run_name": "Strategy Generation"
    },
)

   
    print("\n=== RAW STRATEGY OUTPUT ===")
    print(repr(result.get("output")))
    print("=== END RAW OUTPUT ===\n")
    initial_strategy = json.loads(result["output"])

    reflection_result = reflect_strategy(
    qualification_data=qualification_data,
    initial_strategy=initial_strategy,
    strategy_start_date=strategy_start_date,
    )

    final_strategy = reflection_result["corrected_strategy"]
    if return_evaluation_data:
       return {
        "initial_strategy": initial_strategy,
        "reflection_result": reflection_result,
        "final_strategy": final_strategy,
    }

    return final_strategy


# =========================================================
# HANDOFF ENTRY POINT
# =========================================================

def generate_strategy_from_handoff(strategy_request):

    if hasattr(strategy_request, "model_dump"):
        strategy_request = strategy_request.model_dump(mode="json")

    if not strategy_request.get("interest_event_id"):
        raise ValueError("A verified Interested event is required.")
    qualification_data = dict(strategy_request["qualification_context"])
    research = strategy_request.get("research_context") or {}
    if research:
        # Outreach keeps these contracts separate; Strategy needs both sources.
        qualification_data["research_context"] = research
        qualification_data.setdefault("restaurant", research.get("restaurant", {}))
    strategy_start_date = strategy_request["strategy_start_date"]

    if not strategy_start_date:
        raise ValueError(
            "strategy_start_date is missing from StrategyRequestHandoff."
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

    # Run guardrails on the actual Strategy Agent output
    # BEFORE adding workflow/database metadata.
    guardrail_result = check_strategy(
        data=strategy_data,
        qualification=request_data["qualification_context"],
        start_date=request_data["strategy_start_date"],
    )

    if guardrail_result["errors"]:
        raise ValueError(
            "Strategy failed guardrails: "
            + "; ".join(guardrail_result["errors"])
        )

    if guardrail_result["warnings"]:
        print("\n=== STRATEGY GUARDRAIL WARNINGS ===")
        for warning in guardrail_result["warnings"]:
            print(f"- {warning}")
        print("=== END GUARDRAIL WARNINGS ===\n")

    # Add workflow/database metadata AFTER guardrail validation.
    # Day numbers count from this date; the UI needs it to place each day on the calendar.
    strategy_data["strategy_start_date"] = request_data["strategy_start_date"]

    # Keep which request and which Interested click this strategy answers.
    strategy_data["strategy_request_id"] = request_data.get("strategy_request_id")
    strategy_data["interest_event_id"] = request_data.get("interest_event_id")

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
