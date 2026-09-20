from datetime import datetime
from typing import Optional, Any

from sqlalchemy import (
    String,
    Text,
    DateTime,
    ForeignKey,
    Integer,
    Boolean,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.database import Base


class RestaurantContext(Base):
    """Extra frontend context, stored separately to preserve existing tables."""

    __tablename__ = "restaurant_contexts"

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"), primary_key=True
    )
    data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"), index=True
    )
    # A nullable unique key prevents duplicate active analyses for a restaurant.
    active_restaurant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("restaurants.id"), unique=True, nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), default="queued")
    content_limit: Mapped[int] = mapped_column(Integer, default=30)
    lookback_days: Mapped[int] = mapped_column(Integer, default=90)
    force_refresh: Mapped[bool] = mapped_column(Boolean, default=False)
    context: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    research_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("research_runs.id"), nullable=True
    )
    qualification_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("qualification_runs.id"), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class Restaurant(Base):
    __tablename__ = "restaurants"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    instagram_username: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
    )

    instagram_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    location: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    research_runs = relationship(
        "ResearchRun",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )

    qualification_runs = relationship(
        "QualificationRun",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )

    strategies = relationship(
        "Strategy",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )

    outreach_events = relationship(
        "OutreachEvent",
        back_populates="restaurant",
        cascade="all, delete-orphan",
    )


class ResearchRun(Base):
    __tablename__ = "research_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )

    # -------------------------
    # Research run metadata
    # -------------------------

    schema_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    analysis_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
    )

    source: Mapped[str] = mapped_column(
        String(50),
        default="live",
    )

    analyzed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    content_limit: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    lookback_days: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # -------------------------
    # Research Agent output
    # -------------------------

    profile: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    profile_analysis: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    research_signals: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    content: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    analysis_coverage: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    data_quality: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Complete original Research Agent output
    full_result: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    # -------------------------
    # Error / system metadata
    # -------------------------

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="research_runs",
    )


class QualificationRun(Base):
    __tablename__ = "qualification_runs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Restaurant being qualified
    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )

    # Exact ResearchRun used as evidence
    research_run_id: Mapped[int] = mapped_column(
        ForeignKey("research_runs.id"),
        nullable=False,
        index=True,
    )

    # -------------------------
    # Qualification run metadata
    # -------------------------

    status: Mapped[str] = mapped_column(
        String(50),
        default="completed",
    )

    agent: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # -------------------------
    # Qualification Agent output
    # -------------------------

    qualification: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    decision_rationale: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    marketing_gaps: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    strengths: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    data_limitations: Mapped[Optional[list[Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Complete original Qualification Agent output
    full_result: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )

    # -------------------------
    # Error / system metadata
    # -------------------------

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="qualification_runs",
    )

class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )

    qualification_run_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("qualification_runs.id"),
        nullable=True,
    )

    strategy_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    pdf_path: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )

    approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="strategies",
    )


class OutreachEvent(Base):
    __tablename__ = "outreach_events"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    restaurant_id: Mapped[int] = mapped_column(
        ForeignKey("restaurants.id"),
        nullable=False,
        index=True,
    )

    strategy_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("strategies.id"),
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    recipient_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    next_followup_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    metadata_json: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="outreach_events",
    )
