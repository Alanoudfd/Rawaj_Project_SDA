"""Read the Strategy Agent's 30-day strategy and track which planned days are done.

The Strategy Agent (agents/strategy_agent) saves its result in ``strategies.strategy_data``:
targets, primary gaps, recommended services and a ``thirty_day_plan`` of numbered days. Day
numbers count from ``strategy_start_date`` (older rows fall back to the row's creation date).
Completed days are kept next to that result under ``day_status``; nothing here calls a model.
"""

from copy import deepcopy
from datetime import date, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.schemas import InputModel
from database.models import Restaurant, Strategy

router = APIRouter(prefix="/api/restaurants", tags=["Strategy Agent"])
RestaurantId = Annotated[int, Path(gt=0)]
DayStatus = Literal["Planned", "Completed"]


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


Database = Annotated[Session, Depends(get_db)]


class PlanDay(BaseModel):
    day: int
    date: str
    focus: str
    action: str
    status: DayStatus = "Planned"


class PrimaryGap(BaseModel):
    gap: str
    severity: str
    highlight: str | None = None
    highlight_label: str | None = None
    key_point: str = ""


class RecommendedService(BaseModel):
    service: str
    why_this_service_fits: str = ""


class TrendSupport(BaseModel):
    insight: str
    source_url: str | None = None


class AgentStrategyResponse(BaseModel):
    id: int
    restaurant_id: int
    restaurant_name: str
    approved: bool
    strategy_request_id: str | None = None
    interest_event_id: str | None = None
    start_date: str
    end_date: str
    targets: list[str]
    gaps: list[PrimaryGap]
    services: list[RecommendedService]
    trends: list[TrendSupport]
    days: list[PlanDay]


class DayUpdate(InputModel):
    status: DayStatus


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _items(data: dict, key: str) -> list[dict]:
    value = data.get(key)
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _latest(db: Session, restaurant_id: int) -> Strategy | None:
    rows = db.scalars(
        select(Strategy).where(Strategy.restaurant_id == restaurant_id).order_by(Strategy.id.desc())
    )
    return next(
        (row for row in rows if isinstance(row.strategy_data, dict) and isinstance(row.strategy_data.get("thirty_day_plan"), list)),
        None,
    )


def _start_date(strategy: Strategy) -> date:
    try:
        return date.fromisoformat(str(strategy.strategy_data.get("strategy_start_date")))
    except ValueError:
        return strategy.created_at.date() if strategy.created_at else date.today()


def _plan_days(strategy: Strategy) -> list[dict]:
    """Valid, de-duplicated plan days in day order, with dates and completion status."""
    data, start = strategy.strategy_data, _start_date(strategy)
    done = data.get("day_status") if isinstance(data.get("day_status"), dict) else {}
    days: dict[int, dict] = {}
    for item in _items(data, "thirty_day_plan"):
        number = item.get("day")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1 or number in days:
            continue
        days[number] = {
            "day": number,
            "date": (start + timedelta(days=number - 1)).isoformat(),
            "focus": _text(item.get("focus")),
            "action": _text(item.get("action")),
            "status": "Completed" if done.get(str(number)) == "Completed" else "Planned",
        }
    return [days[number] for number in sorted(days)]


def _response(db: Session, strategy: Strategy) -> dict:
    data = strategy.strategy_data
    days = _plan_days(strategy)
    restaurant = db.get(Restaurant, strategy.restaurant_id)
    return {
        "id": strategy.id,
        "restaurant_id": strategy.restaurant_id,
        "restaurant_name": _text(data.get("restaurant")) or (restaurant.name if restaurant else ""),
        "approved": bool(strategy.approved),
        "strategy_request_id": _text(data.get("strategy_request_id")) or None,
        "interest_event_id": _text(data.get("interest_event_id")) or None,
        "start_date": days[0]["date"] if days else _start_date(strategy).isoformat(),
        "end_date": days[-1]["date"] if days else _start_date(strategy).isoformat(),
        "targets": [text for text in map(_text, data.get("thirty_day_target") or []) if text],
        "gaps": [
            {
                "gap": _text(item.get("gap")), "severity": _text(item.get("severity")),
                "highlight": str(item["highlight"]) if item.get("highlight") not in (None, "") else None,
                "highlight_label": _text(item.get("highlight_label")) or None,
                "key_point": _text(item.get("key_point")),
            }
            for item in _items(data, "primary_marketing_gaps") if _text(item.get("gap"))
        ],
        "services": [
            {"service": _text(item.get("service")), "why_this_service_fits": _text(item.get("why_this_service_fits"))}
            for item in _items(data, "recommended_services") if _text(item.get("service"))
        ],
        "trends": [
            {"insight": _text(item.get("insight")), "source_url": _text(item.get("source_url")) or None}
            for item in _items(data, "external_trend_support") if _text(item.get("insight"))
        ],
        "days": days,
    }


def _require_restaurant(db: Session, restaurant_id: int) -> None:
    if db.get(Restaurant, restaurant_id) is None:
        raise HTTPException(404, "Restaurant not found")


@router.get("/{restaurant_id}/agent-strategy", response_model=AgentStrategyResponse)
def get_agent_strategy(restaurant_id: RestaurantId, db: Database):
    _require_restaurant(db, restaurant_id)
    strategy = _latest(db, restaurant_id)
    if strategy is None:
        raise HTTPException(404, "The Strategy Agent has not produced a strategy for this restaurant yet")
    return _response(db, strategy)


@router.patch("/{restaurant_id}/agent-strategy/days/{day}", response_model=AgentStrategyResponse)
def update_day(restaurant_id: RestaurantId, day: Annotated[int, Path(ge=1)], payload: DayUpdate,
               request: Request, db: Database):
    with request.app.state.restaurant_write_lock:
        _require_restaurant(db, restaurant_id)
        strategy = _latest(db, restaurant_id)
        if strategy is None:
            raise HTTPException(404, "The Strategy Agent has not produced a strategy for this restaurant yet")
        if day not in {item["day"] for item in _plan_days(strategy)}:
            raise HTTPException(404, "Day not found in this restaurant's strategy")
        data = deepcopy(strategy.strategy_data)
        statuses = data["day_status"] if isinstance(data.get("day_status"), dict) else {}
        statuses[str(day)] = payload.status
        data["day_status"] = statuses
        strategy.strategy_data = data
        db.commit()
        return _response(db, strategy)
