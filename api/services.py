"""Database helpers and deferred agent calls for the HTTP application."""

import logging
from datetime import datetime

from sqlalchemy import select

from api.schemas import RestaurantResponse
from database.models import AnalysisJob, QualificationRun, ResearchRun, RestaurantContext

logger = logging.getLogger(__name__)


def restaurant_response(db, restaurant):
    stored_context = db.get(RestaurantContext, restaurant.id)
    response = RestaurantResponse.model_validate(restaurant)
    response.context = stored_context.data if stored_context else {}
    return response


def latest_research(db, restaurant_id):
    return db.scalar(
        select(ResearchRun)
        .where(ResearchRun.restaurant_id == restaurant_id)
        .order_by(ResearchRun.created_at.desc(), ResearchRun.id.desc())
        .limit(1)
    )


def matching_qualification(db, research):
    if research is None:
        return None
    return db.scalar(
        select(QualificationRun)
        .where(
            QualificationRun.restaurant_id == research.restaurant_id,
            QualificationRun.research_run_id == research.id,
            QualificationRun.status == "completed",
        )
        .order_by(QualificationRun.created_at.desc(), QualificationRun.id.desc())
        .limit(1)
    )


def latest_job(db, restaurant_id):
    return db.scalar(
        select(AnalysisJob)
        .where(AnalysisJob.restaurant_id == restaurant_id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .limit(1)
    )


def context_runs(db, restaurant_id):
    job = latest_job(db, restaurant_id)
    if job is not None and job.research_run_id is not None:
        research = db.get(ResearchRun, job.research_run_id)
        if research is not None and research.restaurant_id == restaurant_id:
            qualification = db.get(QualificationRun, job.qualification_run_id) if job.qualification_run_id else None
            if qualification is not None and (
                qualification.restaurant_id != restaurant_id
                or qualification.research_run_id != research.id
                or qualification.status != "completed"
            ):
                qualification = None
            return research, qualification, job
    research = latest_research(db, restaurant_id)
    return research, matching_qualification(db, research), job


def run_workflow(*, session_factory=None, **kwargs):
    from orchestration.workflow import run_restaurant_workflow

    return run_restaurant_workflow(**kwargs, session_factory=session_factory)


def generate_draft(outreach_input):
    from agents.outreach_agent.outreach_agent import run_outreach_agent

    return run_outreach_agent(outreach_input)


def execute_analysis(job_id, session_factory, workflow_runner):
    """Each background job owns its sessions; no request session crosses threads."""
    with session_factory() as db:
        job = db.get(AnalysisJob, job_id)
        if job is None or job.status != "queued":
            return
        job.status = "running"
        job.started_at = datetime.utcnow()
        kwargs = {
            "restaurant_id": job.restaurant_id,
            "content_limit": job.content_limit,
            "lookback_days": job.lookback_days,
            "force_refresh": job.force_refresh,
            "context": job.context,
        }
        db.commit()

    result = {}
    error = None
    try:
        candidate = workflow_runner(**kwargs)
        if not isinstance(candidate, dict):
            raise TypeError("Workflow result must be an object")
        result = candidate
        if result.get("error") or not result.get("qualification_run_id"):
            error = "Analysis failed. Check the server configuration and retry."
    except Exception as exc:
        # Provider exception strings may contain tokens or private request data.
        logger.error("Analysis %s failed (%s)", job_id, type(exc).__name__)
        error = "Analysis failed. Check the server configuration and retry."

    with session_factory() as db:
        job = db.get(AnalysisJob, job_id)
        job.status = "failed" if error else "completed"
        job.error = error
        job.research_run_id = result.get("research_run_id")
        job.qualification_run_id = result.get("qualification_run_id")
        job.active_restaurant_id = None
        job.finished_at = datetime.utcnow()
        db.commit()
