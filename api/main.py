"""FastAPI routes for restaurant data, agent execution, and result retrieval."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from pathlib import Path as FilePath
from threading import Lock
from typing import Annotated
from uuid import uuid4

from fastapi import BackgroundTasks, Body, Depends, FastAPI, HTTPException, Path, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from api import planning, services
from api.schemas import (
    AnalyzeRequest, ContextResponse, JobResponse, OutreachDraft,
    QualificationResponse, ResearchResponse, RestaurantCreate,
    RestaurantList, RestaurantResponse, RestaurantUpdate,
)
from database.database import Base, engine
from database.models import AnalysisJob, Restaurant, RestaurantContext

logger = logging.getLogger(__name__)
RestaurantId = Annotated[int, Path(gt=0)]


def get_db(request: Request):
    with request.app.state.session_factory() as db:
        yield db


Database = Annotated[Session, Depends(get_db)]


def require_restaurant(db, restaurant_id):
    restaurant = db.get(Restaurant, restaurant_id)
    if restaurant is None:
        raise HTTPException(404, "Restaurant not found")
    return restaurant


def require_idle(db, restaurant_id):
    active = db.scalar(
        select(AnalysisJob.id).where(AnalysisJob.active_restaurant_id == restaurant_id)
    )
    if active:
        raise HTTPException(409, {"message": "Analysis is already running", "job_id": active})


def create_app(database_engine=engine, workflow_runner=None, outreach_runner=None):
    session_factory = sessionmaker(bind=database_engine, autoflush=False, expire_on_commit=False)
    restaurant_write_lock = Lock()

    @asynccontextmanager
    async def lifespan(application):
        Base.metadata.create_all(bind=database_engine)
        # This local development API runs in a single server process.
        with session_factory() as db:
            db.execute(
                update(AnalysisJob)
                .where(AnalysisJob.status.in_(["queued", "running"]))
                .values(
                    status="failed", active_restaurant_id=None,
                    finished_at=datetime.utcnow(),
                    error="The server restarted before analysis finished. Run the analysis again.",
                )
            )
            db.commit()
        yield

    application = FastAPI(title="Rawaj API", version="1.0.0", lifespan=lifespan)
    application.state.session_factory = session_factory
    application.state.restaurant_write_lock = restaurant_write_lock
    application.state.content_ideas_runner = planning.generate_content_ideas
    application.include_router(planning.router)
    application.state.workflow_runner = workflow_runner or partial(services.run_workflow, session_factory=session_factory)
    application.state.outreach_runner = outreach_runner or services.generate_draft
    origins = os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173",
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[value.strip().rstrip("/") for value in origins.split(",") if value.strip()],
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type"],
    )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request, exc):
        logger.error("Database operation failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    @application.get("/health", tags=["Health"])
    def health():
        return {"status": "ok"}

    @application.get("/api/restaurants", response_model=RestaurantList, tags=["Restaurants"])
    def list_restaurants(db: Database, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
        restaurants = db.scalars(select(Restaurant).order_by(Restaurant.id).offset(offset).limit(limit)).all()
        return RestaurantList(
            items=[services.restaurant_response(db, item) for item in restaurants],
            total=db.scalar(select(func.count(Restaurant.id))), offset=offset, limit=limit,
        )

    @application.post("/api/restaurants", response_model=RestaurantResponse, status_code=201, tags=["Restaurants"])
    def create_restaurant(payload: RestaurantCreate, db: Database):
        existing = db.scalar(select(Restaurant.id).where(func.lower(Restaurant.instagram_username) == payload.instagram_username))
        if existing:
            raise HTTPException(409, "A restaurant with this Instagram username already exists")
        restaurant = Restaurant(
            **payload.model_dump(exclude={"context"}),
            instagram_url=f"https://www.instagram.com/{payload.instagram_username}/",
        )
        try:
            db.add(restaurant)
            db.flush()
            db.add(RestaurantContext(restaurant_id=restaurant.id, data=payload.context))
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "A restaurant with this Instagram username already exists") from None
        return services.restaurant_response(db, restaurant)

    @application.get("/api/restaurants/{restaurant_id}", response_model=RestaurantResponse, tags=["Restaurants"])
    def get_restaurant(restaurant_id: RestaurantId, db: Database):
        return services.restaurant_response(db, require_restaurant(db, restaurant_id))

    @application.patch("/api/restaurants/{restaurant_id}", response_model=RestaurantResponse, tags=["Restaurants"])
    def update_restaurant(restaurant_id: RestaurantId, payload: RestaurantUpdate, db: Database):
        with restaurant_write_lock:
            restaurant = require_restaurant(db, restaurant_id)
            require_idle(db, restaurant_id)
            values = payload.model_dump(exclude_unset=True)
            if "context" in values:
                context = db.get(RestaurantContext, restaurant_id)
                if context is None:
                    context = RestaurantContext(restaurant_id=restaurant_id)
                    db.add(context)
                context.data = values.pop("context")
            for key, value in values.items():
                setattr(restaurant, key, value)
            restaurant.updated_at = datetime.utcnow()
            db.commit()
            return services.restaurant_response(db, restaurant)

    @application.get("/api/restaurants/{restaurant_id}/context", response_model=ContextResponse, tags=["Restaurants"])
    def get_context(restaurant_id: RestaurantId, db: Database):
        restaurant = require_restaurant(db, restaurant_id)
        research, qualification, job = services.context_runs(db, restaurant_id)
        return ContextResponse(
            restaurant=services.restaurant_response(db, restaurant),
            research=ResearchResponse(
                id=research.id, status=research.status, created_at=research.created_at, result=research.full_result,
            ) if research else None,
            qualification=QualificationResponse(
                id=qualification.id, research_run_id=qualification.research_run_id,
                status=qualification.status, created_at=qualification.created_at, result=qualification.full_result,
            ) if qualification else None,
            latest_job=JobResponse.model_validate(job) if job else None,
        )

    @application.post("/api/restaurants/{restaurant_id}/analyze", response_model=JobResponse, status_code=202, tags=["Agents"])
    def analyze(restaurant_id: RestaurantId, background_tasks: BackgroundTasks, request: Request, db: Database,
                payload: Annotated[AnalyzeRequest, Body()] = AnalyzeRequest()):
        with restaurant_write_lock:
            restaurant = require_restaurant(db, restaurant_id)
            if not restaurant.is_active:
                raise HTTPException(409, "Activate this restaurant before running analysis")
            require_idle(db, restaurant_id)
            context = db.get(RestaurantContext, restaurant_id)
            job = AnalysisJob(
                id=str(uuid4()), restaurant_id=restaurant_id, active_restaurant_id=restaurant_id,
                context=context.data if context else {}, **payload.model_dump(),
            )
            try:
                db.add(job)
                db.commit()
            except IntegrityError:
                db.rollback()
                require_idle(db, restaurant_id)
                raise HTTPException(409, "Could not start analysis; retry the request") from None
            response = JobResponse.model_validate(job)
            background_tasks.add_task(
                services.execute_analysis, job.id, session_factory, request.app.state.workflow_runner,
            )
            return response

    @application.get("/api/jobs/{job_id}", response_model=JobResponse, tags=["Agents"])
    def get_job(job_id: str, db: Database):
        job = db.get(AnalysisJob, job_id)
        if job is None:
            raise HTTPException(404, "Analysis job not found")
        return JobResponse.model_validate(job)

    @application.post("/api/restaurants/{restaurant_id}/outreach/draft", response_model=OutreachDraft, tags=["Agents"])
    def outreach_draft(restaurant_id: RestaurantId, request: Request, db: Database):
        restaurant = require_restaurant(db, restaurant_id)
        require_idle(db, restaurant_id)
        if not restaurant.email:
            raise HTTPException(422, "Add a contact email before generating an outreach draft")
        _, qualification, _ = services.context_runs(db, restaurant_id)
        if qualification is None:
            raise HTTPException(409, "Complete restaurant analysis before generating an outreach draft")
        try:
            draft = request.app.state.outreach_runner({
                "restaurant_name": restaurant.name,
                "email": restaurant.email,
                "marketing_gaps": [
                    item.get("gap", "") if isinstance(item, dict) else str(item)
                    for item in (qualification.marketing_gaps or [])
                ],
                "qualification_summary": qualification.decision_rationale or "",
                "message_type": "initial",
            })
            return OutreachDraft.model_validate(draft.model_dump() if hasattr(draft, "model_dump") else draft)
        except Exception as exc:
            logger.error("Draft generation failed (%s)", type(exc).__name__)
            raise HTTPException(502, "Could not generate the draft. Check server configuration and retry.") from None

    frontend_dist = FilePath(__file__).resolve().parents[1] / "frontend" / "dist"
    application.mount(
        "/assets", StaticFiles(directory=frontend_dist / "assets", check_dir=False), name="frontend-assets"
    )

    @application.get("/", include_in_schema=False)
    def frontend_page():
        index = frontend_dist / "index.html"
        if not index.is_file():
            raise HTTPException(503, "Build the frontend with: npm --prefix frontend run build")
        return FileResponse(index, headers={"Cache-Control": "no-cache"})

    return application


app = create_app()
