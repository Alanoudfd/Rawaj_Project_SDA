from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import (
    Restaurant,
    ResearchRun,
    QualificationRun,
)


def get_restaurant_by_id(
    db: Session,
    restaurant_id: int,
) -> Restaurant | None:

    return db.get(Restaurant, restaurant_id)


def get_restaurant_by_username(
    db: Session,
    instagram_username: str,
) -> Restaurant | None:

    statement = select(Restaurant).where(
        Restaurant.instagram_username == instagram_username
    )

    return db.scalar(statement)


def get_latest_research(
    db: Session,
    restaurant_id: int,
) -> ResearchRun | None:

    statement = (
        select(ResearchRun)
        .where(
            ResearchRun.restaurant_id == restaurant_id,
            ResearchRun.status == "complete",
        )
        .order_by(ResearchRun.analyzed_at.desc())
        .limit(1)
    )

    return db.scalar(statement)


def build_qualification_input(
    research_run: ResearchRun,
) -> dict:

    restaurant = research_run.restaurant

    return {
        "restaurant": {
            "restaurant_id": restaurant.id,
            "name": restaurant.name,
            "instagram_username": restaurant.instagram_username,
            "instagram_url": restaurant.instagram_url,
            "email": restaurant.email,
            "location": restaurant.location,
        },
        "profile": research_run.profile,
        "profile_analysis": research_run.profile_analysis,
        "metrics": research_run.metrics,
        "research_signals": research_run.research_signals,
    }


def _parse_datetime(value: str | None) -> datetime | None:

    if not value:
        return None

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).replace(tzinfo=None)


def save_research_result(
    db: Session,
    restaurant_id: int,
    result: dict,
    content_limit: int | None = None,
    lookback_days: int | None = None,
) -> ResearchRun:

    metadata = result.get("analysis_metadata", {})

    research_run = ResearchRun(
        restaurant_id=restaurant_id,

        schema_version=result.get("schema_version"),

        analysis_version=metadata.get("analysis_version"),

        status=metadata.get("status", "complete"),

        source="live",

        analyzed_at=_parse_datetime(
            metadata.get("analyzed_at")
        ),

        content_limit=content_limit,

        lookback_days=lookback_days,

        profile=result.get("profile"),

        profile_analysis=result.get("profile_analysis"),

        metrics=result.get("metrics"),

        research_signals=result.get("research_signals"),

        content=result.get("content"),

        analysis_coverage=result.get("analysis_coverage"),

        data_quality=result.get("data_quality"),

        full_result=result,
    )

    try:
        db.add(research_run)
        db.commit()
        db.refresh(research_run)

        return research_run

    except Exception:
        db.rollback()
        raise

def save_qualification_result(
    db: Session,
    restaurant_id: int,
    research_run_id: int,
    result: dict,
) -> QualificationRun:
    """
    Save the complete Qualification Agent result.

    The qualification is linked to the exact ResearchRun
    that was used as its evidence.
    """

    qualification_run = QualificationRun(
        restaurant_id=restaurant_id,
        research_run_id=research_run_id,

        status="completed",

        agent=result.get("agent"),

        qualification=result.get("qualification"),
        decision_rationale=result.get("decision_rationale"),

        marketing_gaps=result.get("marketing_gaps"),
        strengths=result.get("strengths"),
        data_limitations=result.get("data_limitations"),

        full_result=result,
    )

    try:
        db.add(qualification_run)
        db.commit()
        db.refresh(qualification_run)

        return qualification_run

    except Exception:
        db.rollback()
        raise 

def get_qualification_for_research(
    db: Session,
    research_run_id: int,
) -> QualificationRun | None:
    """
    Return an existing completed QualificationRun
    for a specific ResearchRun.

    This prevents the Qualification Agent from running
    again on research that has already been qualified.
    """

    statement = (
        select(QualificationRun)
        .where(
            QualificationRun.research_run_id == research_run_id,
            QualificationRun.status == "completed",
        )
        .order_by(QualificationRun.created_at.desc())
        .limit(1)
    )

    return db.scalar(statement)