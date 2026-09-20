import logging
from copy import deepcopy
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END

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
from orchestration.outreach_node import outreach_node

logger = logging.getLogger(__name__)


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
        from agents.research_agent.research_agent import run_research_agent

        restaurant_id = state["restaurant_id"]
        restaurant = db.get(Restaurant, restaurant_id)

        if restaurant is None:
            return {"error": f"Restaurant {restaurant_id} not found.", "next": "end"}

        research_run = get_latest_research(db, restaurant_id)

        if research_run is None:
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
            research_result = research_report.model_dump(mode="json")
            research_run = save_research_result(
                db=db,
                restaurant_id=restaurant.id,
                result=research_result,
                content_limit=30,
                lookback_days=90,
            )

        qualification_input = build_qualification_input(research_run)
        return {
            "research_run_id": research_run.id,
            "qualification_input": qualification_input,
            "next": "check_qualification",
        }

    except Exception as error:
        return {"error": str(error), "next": "end"}

    finally:
        db.close()


def check_qualification_node(state: AgentState):
    db = SessionLocal()

    try:
        research_run_id = state["research_run_id"]
        existing_qualification = get_qualification_for_research(db, research_run_id)

        if existing_qualification:
            return {
                "qualification_run_id": existing_qualification.id,
                "qualification_result": existing_qualification.full_result,
                "next": "outreach",
            }

        return {"next": "qualification"}

    except Exception as error:
        return {"error": str(error), "next": "end"}

    finally:
        db.close()


def qualification_node(state: AgentState):
    db = SessionLocal()

    try:
        from agents.qualification_agent.qualification_agent import run_qualification_agent

        restaurant_id = state["restaurant_id"]
        research_run_id = state["research_run_id"]
        qualification_input = state["qualification_input"]

        qualification_result = run_qualification_agent(qualification_input)
        qualification_run = save_qualification_result(
            db=db,
            restaurant_id=restaurant_id,
            research_run_id=research_run_id,
            result=qualification_result,
        )

        return {
            "qualification_run_id": qualification_run.id,
            "qualification_result": qualification_result,
            "next": "outreach",
        }

    except Exception as error:
        return {"error": str(error), "next": "end"}

    finally:
        db.close()


# =========================================================
# ROUTING
# =========================================================


def route_after_research(state: AgentState):
    if state.get("next") == "check_qualification":
        return "check_qualification"
    return "end"


def route_after_qualification_check(state: AgentState):
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
workflow.add_node("research", research_node)
workflow.add_node("check_qualification", check_qualification_node)
workflow.add_node("qualification", qualification_node)
workflow.add_node("outreach", outreach_node)
workflow.add_edge(START, "research")
workflow.add_conditional_edges(
    "research",
    route_after_research,
    {"check_qualification": "check_qualification", "end": END},
)
workflow.add_conditional_edges(
    "check_qualification",
    route_after_qualification_check,
    {"qualification": "qualification", "outreach": "outreach", "end": END},
)
workflow.add_edge("qualification", "outreach")
workflow.add_edge("outreach", END)

graph = workflow.compile()


# =========================================================
# PUBLIC API
# =========================================================


def _context_compatible(existing_context: Any, requested_context: Any) -> bool:
    previous = existing_context if isinstance(existing_context, dict) else {}
    current = requested_context if isinstance(requested_context, dict) else {}
    return previous == current


def run_restaurant_workflow(
    restaurant_id: int,
    content_limit: int = 30,
    lookback_days: int = 90,
    *,
    context: dict[str, Any] | None = None,
    force_refresh: bool = False,
    session_factory=None,
):
    if not isinstance(restaurant_id, int) or isinstance(restaurant_id, bool) or restaurant_id <= 0:
        raise ValueError("restaurant_id must be a positive integer")

    if not isinstance(content_limit, int) or isinstance(content_limit, bool) or not 1 <= content_limit <= 100:
        raise ValueError("content_limit must be between 1 and 100")

    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or not 1 <= lookback_days <= 365:
        raise ValueError("lookback_days must be between 1 and 365")

    if not isinstance(force_refresh, bool):
        raise ValueError("force_refresh must be a boolean")

    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("context must be a dictionary")

    if session_factory is None:
        session_factory = SessionLocal

    restaurant_context = deepcopy(context)

    with session_factory() as db:
        restaurant = db.get(Restaurant, restaurant_id)
        if restaurant is None:
            return {"error": "Restaurant not found."}

        research_run = None
        if not force_refresh:
            research_run = get_latest_research(
                db,
                restaurant_id,
                content_limit=content_limit,
                lookback_days=lookback_days,
            )

        if research_run is None:
            try:
                restaurant_input = RestaurantInfo(
                    restaurant_id=restaurant.id,
                    name=restaurant.name,
                    instagram_username=restaurant.instagram_username,
                    instagram_url=(
                        restaurant.instagram_url
                        or f"https://www.instagram.com/{restaurant.instagram_username.strip('@')}"
                    ),
                    email=restaurant.email,
                    location=restaurant.location,
                )
                from agents.research_agent.research_agent import run_research_agent

                research_report = run_research_agent(
                    restaurant=restaurant_input,
                    content_limit=content_limit,
                    lookback_days=lookback_days,
                )
                result = research_report.model_dump(mode="json")
                research_run = save_research_result(
                    db=db,
                    restaurant_id=restaurant.id,
                    result=result,
                    content_limit=content_limit,
                    lookback_days=lookback_days,
                )
            except Exception:
                logger.error("Research failed for restaurant %s. Please try again.", restaurant_id)
                return {
                    "restaurant_id": restaurant_id,
                    "error": "Research failed. Please try again.",
                }

        if str(getattr(research_run, "status", "")).lower() == "failed":
            return {
                "restaurant_id": restaurant_id,
                "research_run_id": research_run.id,
                "error": "Research failed. Please try again.",
            }

        existing_qualification = get_qualification_for_research(db, research_run.id)
        previous_context = {}
        if existing_qualification is not None:
            previous_context = existing_qualification.full_result.get("restaurant_context") or {}
        if existing_qualification and _context_compatible(previous_context, restaurant_context):
            return {
                "restaurant_id": restaurant_id,
                "research_run_id": research_run.id,
                "qualification_run_id": existing_qualification.id,
                "qualification_result": existing_qualification.full_result,
            }

        try:
            qualification_input = build_qualification_input(research_run)
            qualification_input["restaurant_context"] = deepcopy(restaurant_context)
            qualification_input["analysis_coverage"] = (
                research_run.analysis_coverage or {"content_requested": content_limit}
            )
            qualification_input["data_quality"] = research_run.data_quality or {}

            from agents.qualification_agent.qualification_agent import run_qualification_agent

            qualification_result = run_qualification_agent(qualification_input)
            qualification_result["restaurant_context"] = deepcopy(restaurant_context)
            qualification_run = save_qualification_result(
                db=db,
                restaurant_id=restaurant_id,
                research_run_id=research_run.id,
                result=qualification_result,
            )
            return {
                "restaurant_id": restaurant_id,
                "research_run_id": research_run.id,
                "qualification_run_id": qualification_run.id,
                "qualification_result": qualification_result,
            }
        except Exception:
            logger.error("Qualification failed for restaurant %s. Please try again.", restaurant_id)
            return {
                "restaurant_id": restaurant_id,
                "research_run_id": research_run.id,
                "error": "Qualification failed. Please try again.",
            }


# =========================================================
# START SYSTEM
# =========================================================


def run_workflow():
    db = SessionLocal()

    try:
        restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()
        restaurant_jobs = [{"id": restaurant.id, "name": restaurant.name} for restaurant in restaurants]
    finally:
        db.close()

    if not restaurant_jobs:
        print("No active restaurants found in the database.")
        return

    print(f"\nFound {len(restaurant_jobs)} active restaurant(s).\n")

    for restaurant in restaurant_jobs:
        print("=" * 60)
        print(f"Processing: {restaurant['name']} (ID: {restaurant['id']})")
        print("=" * 60)

        result = run_restaurant_workflow(restaurant["id"])
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            print()
            continue

        print("Research Run ID:", result.get("research_run_id"))
        print("Qualification Run ID:", result.get("qualification_run_id"))
        qualification_result = result.get("qualification_result", {})
        print("Qualification:", qualification_result.get("qualification"))
        print()


if __name__ == "__main__":
    run_workflow()
