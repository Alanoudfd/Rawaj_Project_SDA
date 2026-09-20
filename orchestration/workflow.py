import logging
from copy import deepcopy
from typing import Any, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from database.database import SessionLocal
from database.models import Restaurant
from database.repository import (
    build_qualification_input,
    get_latest_research,
    get_qualification_for_research,
    save_qualification_result,
    save_research_result,
)


logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    restaurant_id: int
    content_limit: int
    lookback_days: int
    force_refresh: bool
    restaurant_context: dict[str, Any] | None
    research_run_id: int
    qualification_input: dict[str, Any]
    qualification_run_id: int
    qualification_result: dict[str, Any]
    next: str
    error: str | None


def _stage_error(stage: str, error: Exception) -> dict[str, str]:
    # Provider errors can include URLs or credentials. Do not return or log
    # their messages or tracebacks through the public workflow.
    logger.error("%s failed (%s)", stage, type(error).__name__)
    return {"error": f"{stage} failed. Please try again.", "next": "end"}


def _open_session(config: RunnableConfig):
    session_factory = config.get("configurable", {}).get("session_factory") or SessionLocal
    return session_factory()


def research_node(state: AgentState, config: RunnableConfig):
    db = _open_session(config)
    try:
        restaurant_id = state["restaurant_id"]
        restaurant = db.get(Restaurant, restaurant_id)
        if restaurant is None:
            return {"error": "Restaurant not found.", "next": "end"}

        content_limit = state.get("content_limit", 30)
        lookback_days = state.get("lookback_days", 90)
        research_run = None
        if not state.get("force_refresh", False):
            research_run = get_latest_research(
                db,
                restaurant_id,
                content_limit=content_limit,
                lookback_days=lookback_days,
            )

        if research_run is None:
            # Import providers only when work is requested, so reading stored
            # data and importing the API do not require external API keys.
            from agents.research_agent.research_agent import run_research_agent
            from agents.research_agent.research_models import RestaurantInfo

            restaurant_input = RestaurantInfo(
                restaurant_id=restaurant.id,
                name=restaurant.name,
                instagram_username=restaurant.instagram_username,
                instagram_url=restaurant.instagram_url,
                email=restaurant.email,
                location=restaurant.location,
            )
            research_report = run_research_agent(
                restaurant=restaurant_input,
                content_limit=content_limit,
                lookback_days=lookback_days,
            )
            research_run = save_research_result(
                db=db,
                restaurant_id=restaurant.id,
                result=research_report.model_dump(mode="json"),
                content_limit=content_limit,
                lookback_days=lookback_days,
            )

        if research_run.status == "failed":
            return {
                "research_run_id": research_run.id,
                "error": "Research did not produce usable results. Please try again.",
                "next": "end",
            }

        qualification_input = build_qualification_input(
            research_run,
            restaurant_context=state.get("restaurant_context"),
        )
        return {
            "research_run_id": research_run.id,
            "qualification_input": qualification_input,
            "next": "check_qualification",
        }
    except Exception as error:
        return _stage_error("Research", error)
    finally:
        db.close()


def check_qualification_node(state: AgentState, config: RunnableConfig):
    # A frontend submission may change or clear context. Existing runs do not
    # track that input, so only context-free CLI runs reuse qualifications.
    if state.get("restaurant_context") is not None or state.get("force_refresh"):
        return {"next": "qualification"}

    db = _open_session(config)
    try:
        existing_qualification = get_qualification_for_research(
            db, state["research_run_id"]
        )
        if existing_qualification is not None:
            return {
                "qualification_run_id": existing_qualification.id,
                "qualification_result": existing_qualification.full_result,
                "next": "end",
            }
        return {"next": "qualification"}
    except Exception as error:
        return _stage_error("Qualification lookup", error)
    finally:
        db.close()


def qualification_node(state: AgentState, config: RunnableConfig):
    db = _open_session(config)
    try:
        from agents.qualification_agent.qualification_agent import (
            run_qualification_agent,
        )

        qualification_result = run_qualification_agent(state["qualification_input"])
        qualification_run = save_qualification_result(
            db=db,
            restaurant_id=state["restaurant_id"],
            research_run_id=state["research_run_id"],
            result=qualification_result,
        )
        return {
            "qualification_run_id": qualification_run.id,
            "qualification_result": qualification_result,
            "next": "end",
        }
    except Exception as error:
        return _stage_error("Qualification", error)
    finally:
        db.close()


def route_after_research(state: AgentState):
    return "check_qualification" if state.get("next") == "check_qualification" else "end"


def route_after_qualification_check(state: AgentState):
    return "qualification" if state.get("next") == "qualification" else "end"


workflow = StateGraph(AgentState)
workflow.add_node("research", research_node)
workflow.add_node("check_qualification", check_qualification_node)
workflow.add_node("qualification", qualification_node)
workflow.add_edge(START, "research")
workflow.add_conditional_edges(
    "research",
    route_after_research,
    {"check_qualification": "check_qualification", "end": END},
)
workflow.add_conditional_edges(
    "check_qualification",
    route_after_qualification_check,
    {"qualification": "qualification", "end": END},
)
workflow.add_edge("qualification", END)
graph = workflow.compile()


def run_restaurant_workflow(
    restaurant_id: int,
    content_limit: int = 30,
    lookback_days: int = 90,
    force_refresh: bool = False,
    context: dict[str, Any] | None = None,
    session_factory=None,
) -> AgentState:
    """Run research and qualification for a single stored restaurant.

    API callers supply the restaurant's saved context, including an empty dict
    when it has been cleared. Omitting context preserves CLI cache behavior.
    """
    if type(restaurant_id) is not int or restaurant_id < 1:
        raise ValueError("restaurant_id must be a positive integer")
    if type(content_limit) is not int or not 1 <= content_limit <= 100:
        raise ValueError("content_limit must be an integer between 1 and 100")
    if type(lookback_days) is not int or not 1 <= lookback_days <= 365:
        raise ValueError("lookback_days must be an integer between 1 and 365")
    if not isinstance(force_refresh, bool):
        raise ValueError("force_refresh must be a boolean")
    if context is not None and not isinstance(context, dict):
        raise ValueError("context must be an object")

    initial_state: AgentState = {
        "restaurant_id": restaurant_id,
        "content_limit": content_limit,
        "lookback_days": lookback_days,
        "force_refresh": force_refresh,
        "restaurant_context": deepcopy(context),
        "error": None,
    }
    try:
        return graph.invoke(
            initial_state,
            config={"configurable": {"session_factory": session_factory or SessionLocal}},
        )
    except Exception as error:
        return {**initial_state, **_stage_error("Restaurant workflow", error)}


def run_workflow():
    """Keep the existing command-line entry point for all active restaurants."""
    db = SessionLocal()
    try:
        restaurants = db.query(Restaurant).filter(Restaurant.is_active.is_(True)).all()
        restaurant_jobs = [{"id": row.id, "name": row.name} for row in restaurants]
    finally:
        db.close()

    if not restaurant_jobs:
        print("No active restaurants found in the database.")
        return

    print(f"\nFound {len(restaurant_jobs)} active restaurant(s).\n")
    for restaurant in restaurant_jobs:
        print(f"Processing: {restaurant['name']} (ID: {restaurant['id']})")
        result = run_restaurant_workflow(restaurant["id"])
        if result.get("error"):
            print(f"ERROR: {result['error']}\n")
            continue
        print("Research Run ID:", result.get("research_run_id"))
        print("Qualification Run ID:", result.get("qualification_run_id"))
        print("Qualification:", result.get("qualification_result", {}).get("qualification"))
        print()


if __name__ == "__main__":
    run_workflow()
