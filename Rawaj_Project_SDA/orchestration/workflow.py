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


# =========================================================
# STATE
# =========================================================

class AgentState(TypedDict, total=False):
    restaurant_id: int

    research_run_id: int
    qualification_input: dict[str, Any]

    qualification_run_id: int
    qualification_result: dict[str, Any]

    next: str
    error: str | None


# =========================================================
# NODES
# =========================================================

def research_node(state: AgentState):
    db = SessionLocal()

    try:
        restaurant_id = state["restaurant_id"]

        # 1. Get the restaurant
        restaurant = db.get(
            Restaurant,
            restaurant_id,
        )

        if restaurant is None:
            return {
                "error": f"Restaurant {restaurant_id} not found.",
                "next": "end",
            }

        # 2. Check if THIS restaurant already has research
        research_run = get_latest_research(
            db,
            restaurant_id,
        )

        # 3. If there is NO research → run Research Agent
        if research_run is None:

            print(
                f"No research exists for {restaurant.name}."
            )
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

            # 4. Save Research Agent result
            research_run = save_research_result(
                db=db,
                restaurant_id=restaurant.id,
                result=research_result,
                content_limit=30,
                lookback_days=90,
            )
            # Save directly to database
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

        # 5. Otherwise use the existing research
        else:
            print(
                f"Research already exists for {restaurant.name}. "
                f"Using Research Run ID: {research_run.id}"
            )

        # 6. Prepare only the required data for Qualification
        qualification_input = build_qualification_input(
            research_run
        )

        return {
            "research_run_id": research_run.id,
            "qualification_input": qualification_input,
            "next": "check_qualification",
        }

    except Exception as e:
        return {
            "error": str(e),
            "next": "end",
        }

    finally:
        db.close()


def check_qualification_node(state: AgentState):
    """
    Check whether this exact ResearchRun has already
    been qualified.

    If yes:
        reuse the existing QualificationRun.

    If no:
        send it to the Qualification Agent.
    """

    db = SessionLocal()

    try:
        research_run_id = state["research_run_id"]

        existing_qualification = (
            get_qualification_for_research(
                db,
                research_run_id,
            )
        )

        if existing_qualification:

            return {
                "qualification_run_id":
                    existing_qualification.id,

                "qualification_result":
                    existing_qualification.full_result,

                "next": "end",
            }

        return {
            "next": "qualification",
        }

    except Exception as e:
        return {
            "error": str(e),
            "next": "end",
        }

    finally:
        db.close()


def qualification_node(state: AgentState):
    """
    Run the Qualification Agent only when this ResearchRun
    has not already been qualified.

    Save the new result to the database.
    """

    db = SessionLocal()

    try:
        restaurant_id = state["restaurant_id"]
        research_run_id = state["research_run_id"]

        qualification_input = state[
            "qualification_input"
        ]

        qualification_result = (
            run_qualification_agent(
                qualification_input
            )
        )

        qualification_run = (
            save_qualification_result(
                db=db,
                restaurant_id=restaurant_id,
                research_run_id=research_run_id,
                result=qualification_result,
            )
        )

        return {
            "qualification_run_id":
                qualification_run.id,

            "qualification_result":
                qualification_result,

            "next": "end",
        }

    except Exception as e:
        return {
            "error": str(e),
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
    if state.get("next") == "qualification":
        return "qualification"

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
        "check_qualification":
            "check_qualification",

        "end":
            END,
    },
)


# Check Qualification → Qualification Agent OR END
workflow.add_conditional_edges(
    "check_qualification",
    route_after_qualification_check,
    {
        "qualification":
            "qualification",

        "end":
            END,
    },
)


# Qualification → END
workflow.add_edge(
    "qualification",
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
            .filter(
                Restaurant.is_active == True
            )
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
        print(
            "No active restaurants found "
            "in the database."
        )

        return


    print(
        f"\nFound {len(restaurant_jobs)} "
        f"active restaurant(s).\n"
    )


    for restaurant in restaurant_jobs:

        print("=" * 60)

        print(
            f"Processing: "
            f"{restaurant['name']} "
            f"(ID: {restaurant['id']})"
        )

        print("=" * 60)


        initial_state: AgentState = {
            "restaurant_id":
                restaurant["id"],
        }


        result = graph.invoke(
            initial_state
        )


        if result.get("error"):

            print(
                f"ERROR: "
                f"{result['error']}"
            )

            print()

            continue


        print(
            "Research Run ID:",
            result.get(
                "research_run_id"
            ),
        )

        print(
            "Qualification Run ID:",
            result.get(
                "qualification_run_id"
            ),
        )


        qualification_result = (
            result.get(
                "qualification_result",
                {},
            )
        )


        print(
            "Qualification:",
            qualification_result.get(
                "qualification"
            ),
        )

        print()


# =========================================================
# START SYSTEM
# =========================================================

if __name__ == "__main__":
    run_workflow()