import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent

from agents.qualification_agent.tools import search_instagram_benchmark
from agents.qualification_agent.schemas import Report
from agents.qualification_agent.prompt import build_qualification_prompt


load_dotenv()


def _get_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing from the environment.")

    return ChatOpenAI(
        model="gpt-5.6-luna",
        use_responses_api=True,
        api_key=api_key,
    )


def run_qualification_agent(
    evidence: dict,
) -> dict:

    # Build the same prompt used in the notebook
    qualification_prompt = build_qualification_prompt(
        evidence
    )

    # Same tool
    tools = [
        search_instagram_benchmark
    ]

    llm = _get_llm()

    # Same agent structure
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=qualification_prompt
    )

    # Run qualification
    result = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": qualification_prompt
            }
        ]
    })

    # Get the final plain-text qualification report
    final_report = result["messages"][-1].text

    # Same structured-output conversion from notebook
    structured_llm = llm.with_structured_output(
        Report
    )

    structured_result = structured_llm.invoke(f"""
Convert this qualification report into organized JSON.

Rules:
- Extract information only from the report.
- Do not invent data.
- Keep each marketing gap separate.
- Preserve evidence, priority, strengths, and limitations.

Report:
{final_report}
""")

    output = structured_result.model_dump()

    # Correct location of restaurant_id for the new handoff
    output["restaurant_id"] = (
        evidence
        .get("restaurant", {})
        .get("restaurant_id")
    )

    output["agent"] = (
        "Qualification & Marketing Gap Analysis Agent"
    )

    return output