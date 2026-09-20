
from dotenv import load_dotenv

load_dotenv()

from typing import Any

from langchain_openai import ChatOpenAI

from agents.outreach_agent.prompt import (
    INITIAL_OUTREACH_PROMPT,
    FIRST_FOLLOW_UP_PROMPT,
    SECOND_FOLLOW_UP_PROMPT,
    FINAL_FOLLOW_UP_PROMPT,
)

from agents.outreach_agent.schemas import (
    OutreachMessage,
)

from agents.outreach_agent.tools import (
    build_prompt_variables,
    validate_email,
)


# =========================================================
# LLM CONFIGURATION
# =========================================================

llm = ChatOpenAI(
    model="gpt-5.6-luna",
    temperature=1,
)


# =========================================================
# PROMPT SELECTION
# =========================================================

def select_outreach_prompt(
    message_type: str,
):
    """
    Select the appropriate prompt based on the message type.
    """

    prompts = {
        "initial": INITIAL_OUTREACH_PROMPT,
        "follow_up_1": FIRST_FOLLOW_UP_PROMPT,
        "follow_up_2": SECOND_FOLLOW_UP_PROMPT,
        "final": FINAL_FOLLOW_UP_PROMPT,
    }

    if message_type not in prompts:
        raise ValueError(
            f"Unsupported message type: {message_type}"
        )

    return prompts[message_type]


# =========================================================
# GENERATE OUTREACH MESSAGE
# =========================================================

def generate_outreach_message(
    restaurant_name: str,
    email: str,
    marketing_gaps: list[str] | None = None,
    qualification_summary: str | None = None,
    previous_messages: list[str] | None = None,
    follow_up_count: int = 0,
    message_type: str = "initial",
) -> OutreachMessage:
    """
    Generate a personalized outreach email.

    The restaurant name is taken from the provided account data.
    Marketing gaps are internal and should not be disclosed.
    """

    if not restaurant_name.strip():
        raise ValueError(
            "Restaurant name cannot be empty."
        )

    if not validate_email(email):
        raise ValueError(
            "Invalid restaurant email."
        )

    prompt = select_outreach_prompt(
        message_type=message_type
    )

    prompt_variables = build_prompt_variables(
        restaurant_name=restaurant_name,
        marketing_gaps=marketing_gaps,
        qualification_summary=qualification_summary,
        previous_messages=previous_messages,
        follow_up_count=follow_up_count,
    )

    structured_llm = llm.with_structured_output(
        OutreachMessage
    )

    chain = prompt | structured_llm

    result = chain.invoke(prompt_variables)

    return result


# =========================================================
# RUN OUTREACH AGENT
# =========================================================

def run_outreach_agent(
    outreach_input: dict[str, Any],
) -> OutreachMessage:
    """
    Run the Outreach Agent using prepared input data.
    """

    restaurant_name = outreach_input.get(
        "restaurant_name",
        ""
    )

    email = outreach_input.get(
        "email",
        ""
    )

    marketing_gaps = outreach_input.get(
        "marketing_gaps",
        []
    )

    qualification_summary = outreach_input.get(
        "qualification_summary",
        ""
    )

    previous_messages = outreach_input.get(
        "previous_messages",
        []
    )

    follow_up_count = outreach_input.get(
        "follow_up_count",
        0
    )

    message_type = outreach_input.get(
        "message_type",
        "initial"
    )

    return generate_outreach_message(
        restaurant_name=restaurant_name,
        email=email,
        marketing_gaps=marketing_gaps,
        qualification_summary=qualification_summary,
        previous_messages=previous_messages,
        follow_up_count=follow_up_count,
        message_type=message_type,
    )