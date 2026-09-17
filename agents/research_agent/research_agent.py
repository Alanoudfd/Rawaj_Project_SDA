import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
##from .research_prompt import RESEARCH_AGENT_PROMPT

from .research_models import (
    AnalysisCoverage,
    AnalysisDateRange,
    AnalysisMetadata,
    AnalyzedContent,
    DataQuality,
    FailedAnalysis,
    InstagramProfile,
    ProfileAnalysis,
    ResearchMetrics,
    ResearchProfile,
    ResearchSignal,
    RestaurantInfo,
)
from .research_tools import (
    analyze_instagram_content,
    analyze_instagram_profile,
    build_research_signals,
    calculate_research_metrics,
    enrich_reels_for_recent_content,
    scrape_instagram_profile,
    scrape_recent_instagram_content,
)

load_dotenv()
DEFAULT_CONTENT_LIMIT = 30
DEFAULT_LOOKBACK_DAYS = 90


# =========================================================
# RESEARCH AGENT
# =========================================================
def run_research_agent(
    restaurant: RestaurantInfo,
    content_limit: int = DEFAULT_CONTENT_LIMIT,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> ResearchProfile:
   

    if content_limit <= 0:
        raise ValueError("content_limit must be greater than 0")

    run_started_at = datetime.now(timezone.utc).isoformat()
    username = restaurant.instagram_username

    # 1) Scrape the Instagram profile.
    profile_raw = scrape_instagram_profile(username)
    profile = InstagramProfile.model_validate(profile_raw)

    # 2) Analyze the already-scraped profile with the LLM.
    profile_analysis_raw = analyze_instagram_profile(
        profile=profile.model_dump(),
        known_email=restaurant.email,
        known_location=restaurant.location,
    )
    profile_analysis = ProfileAnalysis.model_validate(profile_analysis_raw)

    # 3) Scrape one recent-content window.
    recent_content = scrape_recent_instagram_content(
        username=username,
        limit=content_limit,
        lookback_days=lookback_days,
    )

    # 4) Enrich Reel items that belong to that same content window.
    enriched_content = enrich_reels_for_recent_content(
        username=username,
        recent_content=recent_content,
    )

    # 5) Analyze each scraped content item with the LLM.
    analyzed_content_raw = analyze_instagram_content(enriched_content)
    analyzed_content = [
        AnalyzedContent.model_validate(item) for item in analyzed_content_raw
    ]

    # 6) Calculate deterministic metrics from the analyzed evidence.
    metrics_raw = calculate_research_metrics(
        profile=profile.model_dump(),
        analyzed_content=analyzed_content_raw,
    )
    metrics = ResearchMetrics.model_validate(metrics_raw)

    # 7) Build descriptive, evidence-backed signals for qualification handoff.
    research_signals_raw = build_research_signals(
        metrics=metrics.model_dump(),
        analyzed_content=analyzed_content_raw,
    )
    research_signals = [
        ResearchSignal.model_validate(item) for item in research_signals_raw
    ]

    coverage = _build_coverage(
        content_limit=content_limit,
        scraped_content=enriched_content,
        analyzed_content=analyzed_content_raw,
    )

    data_quality = _build_data_quality(
        profile=profile.model_dump(),
        scraped_content=enriched_content,
        analyzed_content=analyzed_content_raw,
        reel_enrichment_called=True,
    )

    report = ResearchProfile(
        restaurant=restaurant,
        analysis_metadata=AnalysisMetadata(
            status=data_quality.status,
            analyzed_at=run_started_at,
        ),
        profile=profile,
        profile_analysis=profile_analysis,
        metrics=metrics,
        research_signals=research_signals,
        content=analyzed_content,
        analysis_coverage=coverage,
        data_quality=data_quality,
    )

    return report
# def run_research_pipeline(
#     restaurant_id: int,
#     name: str,
#     instagram_username: str,
#     email: str | None = None,
#     location: str | None = None,
#     content_limit: int = 15,
#     lookback_days: int = 90,
# ) -> dict:
#     """
#     Run the complete Instagram research workflow for one restaurant.

#     Executes profile scraping, profile analysis, recent-content scraping,
#     Reel enrichment, content analysis, deterministic metric calculation,
#     and research-signal generation.

#     Returns the complete validated ResearchProfile.
#     """

#     restaurant = RestaurantInfo(
#         restaurant_id=restaurant_id,
#         name=name,
#         instagram_username=instagram_username,
#         email=email,
#         location=location,
#     )

#     report, output_path = run_research_agent(
#         restaurant=restaurant,
#         content_limit=content_limit,
#         lookback_days=lookback_days,
#     )

#     return {
#         "research_profile": report.model_dump(mode="json"),
#         "output_path": str(output_path),
#     }

# RESEARCH_TOOLS = [
#     run_research_pipeline,
# ]


# research_llm = ChatOpenAI(
#     model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
#     use_responses_api=True,
#     timeout=120,
#     max_retries=3,
# )



# research_agent = create_agent(
#     model=research_llm,
#     tools=RESEARCH_TOOLS,
#     system_prompt=RESEARCH_AGENT_PROMPT,
# )




# =========================================================
# HELPERS
# =========================================================


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value.strip())
    return cleaned.strip("_") or "instagram_account"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _build_coverage(
    content_limit: int,
    scraped_content: list[dict],
    analyzed_content: list[dict],
) -> AnalysisCoverage:
    analyzed_models = [AnalyzedContent.model_validate(item) for item in analyzed_content]

    successful = [
        item
        for item in analyzed_models
        if item.analysis is not None and not item.analysis_error
    ]
    failed = [
        item
        for item in analyzed_models
        if item.analysis is None or item.analysis_error
    ]

    dates = [
        parsed
        for parsed in (_parse_timestamp(item.raw_data.timestamp) for item in analyzed_models)
        if parsed is not None
    ]

    reels = [item for item in analyzed_models if item.reel_details is not None]
    enriched_reels = [
        item
        for item in reels
        if item.reel_details and item.reel_details.enrichment_success
    ]
    transcript_count = sum(
        1
        for item in enriched_reels
        if item.reel_details and item.reel_details.transcript
    )

    return AnalysisCoverage(
        content_requested=content_limit,
        content_scraped=len(scraped_content),
        content_analyzed=len(successful),
        content_failed=len(failed),
        analysis_success_pct=(
            round((len(successful) / len(scraped_content)) * 100, 2)
            if scraped_content
            else 0.0
        ),
        date_range=AnalysisDateRange(
            oldest_content=min(dates).isoformat() if dates else None,
            newest_content=max(dates).isoformat() if dates else None,
        ),
        multimodal_analysis=bool(successful),
        reels_detected=len(reels),
        reels_enriched=len(enriched_reels),
        reel_transcripts_available=transcript_count,
    )


def _build_data_quality(
    profile: dict | None,
    scraped_content: list[dict],
    analyzed_content: list[dict],
    reel_enrichment_called: bool,
) -> DataQuality:
    analyzed_models = [AnalyzedContent.model_validate(item) for item in analyzed_content]

    failed_records: list[FailedAnalysis] = []
    warnings: list[str] = []

    for item in analyzed_models:
        if item.analysis_error:
            failed_records.append(
                FailedAnalysis(
                    content_id=item.content_id,
                    stage="multimodal_analysis",
                    reason=item.analysis_error,
                )
            )

    reel_items = [item for item in analyzed_models if item.reel_details is not None]

    if reel_items:
        warnings.append(
            "Reel/video visual analysis uses supplied cover/images plus transcript when available; full raw video frames are not analyzed."
        )
        no_transcript = [
            item.content_id
            for item in reel_items
            if item.reel_details and not item.reel_details.transcript
        ]
        if no_transcript:
            warnings.append(
                f"No Reel transcript was available for {len(no_transcript)} matched Reel item(s)."
            )

    # Normal video items that were not matched as Reels are still analyzed.
    unmatched_videos = [
        item.content_id
        for item in analyzed_models
        if (
            str(item.raw_data.content_type or "").lower() == "video"
            and item.reel_details is None
        )
    ]
    if unmatched_videos:
        warnings.append(
            f"{len(unmatched_videos)} video item(s) were not matched by the Reel scraper; they were analyzed using caption, engagement metadata, and available cover/images."
        )

    profile_ok = bool(profile)
    scrape_ok = bool(scraped_content)
    successful_count = sum(
        1
        for item in analyzed_models
        if item.analysis is not None and not item.analysis_error
    )
    multimodal_complete = bool(analyzed_models) and successful_count == len(analyzed_models)

    reel_enrichment_complete = True
    if reel_items:
        reel_enrichment_complete = all(
            item.reel_details is not None and item.reel_details.enrichment_success
            for item in reel_items
        )

    if profile_ok and scrape_ok and multimodal_complete:
        status = "complete"
    elif profile_ok or scrape_ok or successful_count > 0:
        status = "partial"
    else:
        status = "failed"

    return DataQuality(
        status=status,
        profile_scrape_success=profile_ok,
        content_scrape_success=scrape_ok,
        multimodal_analysis_completed=multimodal_complete,
        reel_enrichment_attempted=reel_enrichment_called,
        reel_enrichment_completed=reel_enrichment_complete,
        warnings=warnings,
        failed_analyses=failed_records,
    )


def save_research_profile(report: ResearchProfile) -> Path:
    """Save every run automatically as a timestamped JSON file."""

    output_dir = Path("results")
    output_dir.mkdir(parents=True, exist_ok=True)

    username = _safe_filename(report.restaurant.instagram_username)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{username}_research_{timestamp}.json"

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(
            report.model_dump(mode="json"),
            file,
            indent=2,
            ensure_ascii=False,
        )

    return output_path

# =========================================================
# STANDALONE RESEARCH AGENT
# =========================================================