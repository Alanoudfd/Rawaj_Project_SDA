from typing import TypedDict, Any

from langgraph.graph import StateGraph, START, END

from agents.research_agent.research_agent import (
    run_research_agent,
)

from agents.research_agent.research_models import (
    RestaurantInfo,
)

from database.database import SessionLocal
from database.models import Restaurant
from database.repository import (
    get_latest_research,
    get_qualification_for_research,
    build_qualification_input,
    save_research_result,
    save_qualification_result,
)

from agents.qualification_agent.qualification_agent import (
    run_qualification_agent,
)
from orchestration.outreach_node import outreach_node


# =========================================================
# STATE
# =========================================================


class AgentState(TypedDict, total=False):
    restaurant_id: int

    research_run_id: int
    qualification_input: dict[str, Any]

    qualification_run_id: int
    qualification_result: dict[str, Any]

    # Existing team routing fields.
    next: str
    error: str | None

    # Outreach & Follow-Up result returned to the shared pipeline.
    outreach_thread_id: str
    outreach_status: str
    outreach_action: str
    outreach_message_id: str
    outreach_pending_human_approval: bool
    outreach_errors: list[str]


# =========================================================
# NODES
# =========================================================


def research_node(state: AgentState):
    db = SessionLocal()

    try:
        restaurant_id = state["restaurant_id"]

        # 1. Get the restaurant.
        restaurant = db.get(
            Restaurant,
            restaurant_id,
        )

        if restaurant is None:
            return {
                "error": f"Restaurant {restaurant_id} not found.",
                "next": "end",
            }

        # 2. Check whether this restaurant already has Research output.
        research_run = get_latest_research(
            db,
            restaurant_id,
        )

        # 3. If there is no Research output, run Research Agent and save it once.
        if research_run is None:
            print(f"No research exists for {restaurant.name}.")
            print("Running Research Agent...")

            restaurant_input = RestaurantInfo(
                restaurant_id=restaurant.id,
                name=restaurant.name,
                instagram_username=restaurant.instagram_username,
                email=restaurant.email,
                location=restaurant.location,
            )

            research_report = run_research_agent(
                restaurant=restaurant_input,
                content_limit=30,
                lookback_days=90,
            )
            research_result = research_report.model_dump(
                mode="json"
            )

            research_run = save_research_result(
                db=db,
                restaurant_id=restaurant.id,
                result=research_result,
                content_limit=30,
                lookback_days=90,
            )

            print(
                f"Research completed and saved. "
                f"Research Run ID: {research_run.id}"
            )

        # 4. Otherwise use the existing Research output.
        else:
            print(
                f"Research already exists for {restaurant.name}. "
                f"Using Research Run ID: {research_run.id}"
            )

        # 5. Prepare only the required data for Qualification.
        qualification_input = build_qualification_input(
            research_run
        )

        return {
            "research_run_id": research_run.id,
            "qualification_input": qualification_input,
            "next": "check_qualification",
        }

    except Exception as error:
        return {
            "error": str(error),
            "next": "end",
        }

    finally:
        db.close()


def check_qualification_node(state: AgentState):
    """Reuse the Qualification output for this exact Research run when present."""

    db = SessionLocal()

    try:
        research_run_id = state["research_run_id"]

        existing_qualification = get_qualification_for_research(
            db,
            research_run_id,
        )

        if existing_qualification:
            return {
                "qualification_run_id": existing_qualification.id,
                "qualification_result": existing_qualification.full_result,
                # Existing qualified data still enters Outreach.
                "next": "outreach",
            }

        return {
            "next": "qualification",
        }

    except Exception as error:
        return {
            "error": str(error),
            "next": "end",
        }

    finally:
        db.close()


def qualification_node(state: AgentState):
    """Run Qualification only when this Research run has not yet been qualified."""

    db = SessionLocal()

    try:
        restaurant_id = state["restaurant_id"]
        research_run_id = state["research_run_id"]
        qualification_input = state["qualification_input"]

        qualification_result = run_qualification_agent(
            qualification_input
        )

        qualification_run = save_qualification_result(
            db=db,
            restaurant_id=restaurant_id,
            research_run_id=research_run_id,
            result=qualification_result,
        )

        return {
            "qualification_run_id": qualification_run.id,
            "qualification_result": qualification_result,
            # Newly saved Qualification output enters Outreach too.
            "next": "outreach",
        }

    except Exception as error:
        return {
            "error": str(error),
            "next": "end",
        }

    finally:
        db.close()


# =========================================================
# ROUTING
# =========================================================


def route_after_research(
    state: AgentState,
):
    if state.get("next") == "check_qualification":
        return "check_qualification"

    return "end"


def route_after_qualification_check(
    state: AgentState,
):
    next_node = state.get("next")

    if next_node == "qualification":
        return "qualification"

    if next_node == "outreach":
        return "outreach"

    return "end"


# =========================================================
# GRAPH
# =========================================================


workflow = StateGraph(AgentState)

workflow.add_node(
    "research",
    research_node,
)

workflow.add_node(
    "check_qualification",
    check_qualification_node,
)

workflow.add_node(
    "qualification",
    qualification_node,
)

workflow.add_node(
    "outreach",
    outreach_node,
)


# START → Research
workflow.add_edge(
    START,
    "research",
)


# Research → Check Qualification OR END
workflow.add_conditional_edges(
    "research",
    route_after_research,
    {
        "check_qualification": "check_qualification",
        "end": END,
    },
)


# Check Qualification → Qualification Agent, Outreach, OR END
workflow.add_conditional_edges(
    "check_qualification",
    route_after_qualification_check,
    {
        "qualification": "qualification",
        "outreach": "outreach",
        "end": END,
    },
)


# Newly produced Qualification output enters Outreach. The outer graph ends after
# Outreach safely pauses for Human Approval, rejects an unqualified restaurant,
# or returns a truthful integration error.
workflow.add_edge(
    "qualification",
    "outreach",
)
workflow.add_edge(
    "outreach",
    END,
)


# =========================================================
# COMPILE
# =========================================================


graph = workflow.compile()


# =========================================================
# RUN DATABASE WORKFLOW
# =========================================================


def run_workflow():
    db = SessionLocal()

    try:
        restaurants = (
            db.query(Restaurant)
            .filter(Restaurant.is_active == True)
            .all()
        )

        restaurant_jobs = [
            {
                "id": restaurant.id,
                "name": restaurant.name,
            }
            for restaurant in restaurants
        ]

    finally:
        db.close()

    if not restaurant_jobs:
        print("No active restaurants found in the database.")
        return

    print(f"\nFound {len(restaurant_jobs)} active restaurant(s).\n")

    for restaurant in restaurant_jobs:
        print("=" * 60)
        print(
            f"Processing: {restaurant['name']} "
            f"(ID: {restaurant['id']})"
        )
        print("=" * 60)

        initial_state: AgentState = {
            "restaurant_id": restaurant["id"],
        }

        result = graph.invoke(initial_state)

        if result.get("error"):
            print(f"ERROR: {result['error']}")
            print()
            continue

        print("Research Run ID:", result.get("research_run_id"))
        print(
            "Qualification Run ID:",
            result.get("qualification_run_id"),
        )

        qualification_result = result.get(
            "qualification_result",
            {},
        )

        print(
            "Qualification:",
            qualification_result.get("qualification"),
        )
        print("Outreach status:", result.get("outreach_status"))
        print("Outreach action:", result.get("outreach_action"))

        if result.get("outreach_pending_human_approval"):
            print(
                "Outreach is paused for Human Approval; "
                "no email has been sent."
            )

        if result.get("outreach_errors"):
            print("Outreach errors:", result["outreach_errors"])

        print()


# =========================================================
# START SYSTEM
# =========================================================


if __name__ == "__main__":
    run_workflow()
