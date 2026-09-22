"""HTTP endpoints for the Post Workspace: confirm the facts, generate the Post Kit, rewrite the caption.

The business logic (prompts, schemas, validation, repair) lives in ``agents.strategy_agent.post_kit`` and is wired in
as ``request.app.state.facts_plan_runner`` / ``post_kit_runner`` / ``caption_rewrite_runner`` (see api/main.py) so it
can be swapped out in tests. This module only builds the context each call needs from the database and shapes the
response; it calls no model itself.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import Field
from sqlalchemy.orm import Session

from agents.strategy_agent.content_ideas import Idea
from agents.strategy_agent.post_kit import (
    PostFacts,
    PostKitInvalid,
    PostKitUnavailable,
    Rewrite,
    crop_rules,
    make_facts_plan,
    make_post_kit,
    make_rewrite,
)
from api import agent_strategy
from api.schemas import InputModel
from database.models import Restaurant

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/restaurants", tags=["Post Kit"])
RestaurantId = Annotated[int, Path(gt=0)]
Day = Annotated[int, Path(ge=1)]


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


Database = Annotated[Session, Depends(get_db)]


def _restaurant_context(restaurant: Restaurant) -> dict:
    return {"name": restaurant.name, "location": restaurant.location or ""}


def _task_context(item: dict, occasions: list[dict]) -> dict:
    return {
        "day": item["day"], "date": item["date"], "focus": item["focus"], "action": item["action"],
        "content_format": item.get("format"),
        "occasions": [occasion["name"] for occasion in occasions if occasion["start_date"] <= item["date"] <= occasion["end_date"]],
    }


def _find_day(db: Session, restaurant_id: int, day: int) -> tuple[dict, dict]:
    """The current strategy's overview and its entry for `day`, or an HTTPException explaining why either is missing."""
    agent_strategy._require_restaurant(db, restaurant_id)
    strategy = agent_strategy._latest(db, restaurant_id)
    if strategy is None:
        raise HTTPException(404, "No strategy has been saved for this restaurant yet")
    overview = agent_strategy._response(db, strategy)
    item = next((entry for entry in overview["days"] if entry["day"] == day), None)
    if item is None:
        raise HTTPException(404, "Day not found in this restaurant's strategy")
    return overview, item


class FactsPlanRequest(InputModel):
    idea: Idea


@router.post("/{restaurant_id}/agent-strategy/days/{day}/post-kit/facts-plan")
def post_facts_plan(restaurant_id: RestaurantId, day: Day, payload: FactsPlanRequest, request: Request, db: Database):
    """What the owner must confirm before a caption is written for this idea."""
    overview, item = _find_day(db, restaurant_id, day)
    restaurant = db.get(Restaurant, restaurant_id)
    context = {
        "restaurant": _restaurant_context(restaurant),
        "task": _task_context(item, overview["occasions"]),
        "idea": payload.idea.model_dump(),
    }
    runner = getattr(request.app.state, "facts_plan_runner", make_facts_plan)
    return runner(context).model_dump()


class CreatePostKitRequest(InputModel):
    idea: Idea
    facts: PostFacts
    tone: str = "warm"


@router.post("/{restaurant_id}/agent-strategy/days/{day}/post-kit")
def post_post_kit(restaurant_id: RestaurantId, day: Day, payload: CreatePostKitRequest, request: Request, db: Database):
    """The Post Kit for the idea the owner chose and the facts they confirmed."""
    overview, item = _find_day(db, restaurant_id, day)
    restaurant = db.get(Restaurant, restaurant_id)
    context = {
        "restaurant": _restaurant_context(restaurant),
        "task": _task_context(item, overview["occasions"]),
        "idea": payload.idea.model_dump(),
        "facts": payload.facts.model_dump(),
        "tone": payload.tone,
        "strategy": {key: overview.get(key) for key in ("summary", "focus", "targets", "pillars", "gaps", "services")},
        "voice": {"recent_captions": []},  # no caption history is stored yet; the account's own voice is not sampled
        "allowed": {"handles": [restaurant.instagram_username] if restaurant.instagram_username else []},
    }
    runner = getattr(request.app.state, "post_kit_runner", make_post_kit)
    try:
        result = runner(context)
    except PostKitUnavailable:
        raise HTTPException(503, "The Post Kit is unavailable. Configure OPENAI_API_KEY in the project's .env file.") from None
    except PostKitInvalid as exc:
        raise HTTPException(502, f"Could not produce a Post Kit that passes every check: {exc}") from None
    except Exception as exc:
        logger.error("Post Kit generation failed (%s): %s", type(exc).__name__, exc)
        raise HTTPException(502, "Could not generate the Post Kit. Check the server configuration and retry.") from None
    return {
        **result.model_dump(),
        "crop_rules": crop_rules(result.kit.shoot.format),
        "best_time": {
            "status": "not_enough_data", "sample_size": 0, "timezone": "Riyadh time",
            "basis": "Not enough of your own posts are tracked yet to find your best time.",
            "general": {
                "label": "Evening",
                "note": "As a starting point, try the evening: a general suggestion for restaurants, not taken from your account.",
            },
        },
    }


class RewriteRequest(InputModel):
    caption: Annotated[str, Field(min_length=1, max_length=1200)]
    change: str
    facts: PostFacts
    content_format: str


@router.post("/{restaurant_id}/agent-strategy/days/{day}/post-kit/rewrite")
def post_rewrite(restaurant_id: RestaurantId, day: Day, payload: RewriteRequest, request: Request, db: Database) -> Rewrite:
    """The current caption, rewritten with one requested change."""
    agent_strategy._require_restaurant(db, restaurant_id)
    restaurant = db.get(Restaurant, restaurant_id)
    context = {
        "restaurant": _restaurant_context(restaurant),
        "task": {"content_format": payload.content_format},
        "facts": payload.facts.model_dump(),
        "caption": payload.caption,
        "change": payload.change,
    }
    runner = getattr(request.app.state, "caption_rewrite_runner", make_rewrite)
    try:
        return runner(context)
    except KeyError:
        raise HTTPException(422, f"Unknown caption change: {payload.change}") from None
    except PostKitUnavailable:
        raise HTTPException(503, "Rewriting is unavailable. Configure OPENAI_API_KEY in the project's .env file.") from None
    except PostKitInvalid as exc:
        raise HTTPException(502, f"The rewritten caption broke a rule: {exc}") from None
    except Exception as exc:
        logger.error("Caption rewrite failed (%s): %s", type(exc).__name__, exc)
        raise HTTPException(502, "Could not rewrite the caption. Check the server configuration and retry.") from None
