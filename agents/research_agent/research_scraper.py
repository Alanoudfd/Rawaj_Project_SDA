"""
PART 1 OF THE RESEARCH AGENT — SCRAPE

Collects raw Instagram data for ONE restaurant through Apify:

1. the public profile
2. the recent content window (images, carousels, videos, Reels)
3. Reel details for the Reels inside that window

Nothing in this module calls an LLM or interprets the data. Part 2
(research_analyzer) turns the result into research evidence.
"""

import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from apify_client import ApifyClient
from dotenv import load_dotenv

from .research_schemas import (
    ContentRawData,
    InstagramProfile,
    ReelDetails,
    ScrapedContent,
    ScrapedInstagramData,
)

load_dotenv()

logger = logging.getLogger(__name__)


# =========================================================
# CONFIGURATION
# =========================================================

PROFILE_ACTOR = "apify/instagram-profile-scraper"
POST_ACTOR = "apify/instagram-post-scraper"
REEL_ACTOR = "apify/instagram-reel-scraper"


# =========================================================
# INTERNAL HELPERS
# =========================================================


def _get_apify_client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise ValueError("APIFY_API_TOKEN is missing from .env")
    return ApifyClient(token)


def _run_apify_actor(actor_id: str, run_input: dict) -> list[dict[str, Any]]:
    client = _get_apify_client()
    run = client.actor(actor_id).call(run_input=run_input)

    if run is None:
        raise RuntimeError(f"Apify actor failed: {actor_id}")

    dataset_id = getattr(run, "default_dataset_id", None)
    if dataset_id is None and isinstance(run, dict):
        dataset_id = run.get("defaultDatasetId")

    if not dataset_id:
        raise RuntimeError(f"No dataset returned by actor: {actor_id}")

    return list(client.dataset(dataset_id).iterate_items())


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shortcode_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([^/?#]+)/?", url)
    return match.group(1) if match else None


def _extract_images(item: dict) -> list[str]:
    urls: list[str] = []

    for url in item.get("images") or []:
        if isinstance(url, str) and url:
            urls.append(url)

    display_url = item.get("displayUrl") or item.get("display_url")
    if display_url:
        urls.append(display_url)

    image_url = item.get("imageUrl") or item.get("thumbnailUrl")
    if image_url:
        urls.append(image_url)

    for child in item.get("childPosts") or []:
        if not isinstance(child, dict):
            continue
        child_display = child.get("displayUrl") or child.get("display_url")
        if child_display:
            urls.append(child_display)
        for url in child.get("images") or []:
            if isinstance(url, str) and url:
                urls.append(url)

    return list(dict.fromkeys(urls))


def _normalize_profile(raw: dict) -> dict:
    return {
        "username": raw.get("username"),
        "full_name": raw.get("fullName"),
        "bio": raw.get("biography"),
        "followers": raw.get("followersCount"),
        "following": raw.get("followsCount"),
        "posts_count": raw.get("postsCount"),
        "website": raw.get("externalUrl"),
        "verified": raw.get("verified"),
        "business_category": raw.get("businessCategoryName"),
        "is_business": raw.get("isBusinessAccount"),
        "is_private": raw.get("private"),
    }


def _normalize_content_item(raw: dict) -> dict:
    short_code = raw.get("shortCode") or raw.get("shortcode")
    url = raw.get("url")

    return ScrapedContent(
        content_id=str(raw.get("id")) if raw.get("id") is not None else None,
        short_code=short_code or _shortcode_from_url(url),
        raw_data=ContentRawData(
            content_url=url,
            timestamp=raw.get("timestamp"),
            caption=raw.get("caption") or "",
            content_type=raw.get("type"),
            product_type=raw.get("productType") or raw.get("product_type"),
            image_urls=_extract_images(raw),
            likes=raw.get("likesCount") if raw.get("likesCount") is not None else raw.get("likes"),
            comments=(
                raw.get("commentsCount")
                if raw.get("commentsCount") is not None
                else raw.get("comments")
            ),
            views=(
                raw.get("videoViewCount")
                or raw.get("videoPlayCount")
                or raw.get("viewCount")
                or raw.get("views")
            ),
            hashtags=raw.get("hashtags") or [],
            mentions=raw.get("mentions") or [],
            alt_text=raw.get("alt") or raw.get("accessibility"),
            music_info=raw.get("musicInfo"),
        ),
    ).model_dump()


def _normalize_reel_details(raw: dict) -> ReelDetails:
    duration = raw.get("videoDuration") or raw.get("duration")
    if duration is not None:
        try:
            duration = float(duration)
        except (TypeError, ValueError):
            duration = None

    return ReelDetails(
        matched=True,
        reel_url=raw.get("url"),
        transcript=raw.get("transcript") or raw.get("videoTranscript"),
        duration_seconds=duration,
        shares=raw.get("sharesCount") or raw.get("reshareCount"),
        plays=raw.get("videoPlayCount") or raw.get("playCount"),
        views=raw.get("videoViewCount") or raw.get("viewCount") or raw.get("igPlayCount"),
        enrichment_success=True,
    )


# =========================================================
# STEP 1 — SCRAPE THE PROFILE
# =========================================================


def scrape_instagram_profile(username: str) -> dict:
    """
    Scrape the public Instagram profile for one restaurant.

    Returns bio, followers, following, post count, website, business
    category, verification status, and account metadata.

    Args:
        username: Instagram username without the @ symbol.
    """

    results = _run_apify_actor(
        PROFILE_ACTOR,
        {
            "usernames": [username],
            "includeAboutSection": False,
        },
    )

    if not results:
        raise ValueError(f"No Instagram profile found for @{username}")

    return _normalize_profile(results[0])


# =========================================================
# STEP 2 — SCRAPE THE RECENT CONTENT WINDOW
# =========================================================


def scrape_recent_instagram_content(
    username: str,
    limit: int = 30,
    lookback_days: int = 90,
) -> list[dict]:
    """
    Scrape the restaurant's recent Instagram content.

    Retrieves one recent content window containing images, carousels,
    videos, and Reels when available. Content is filtered using the
    specified lookback period.

    Args:
        username: Instagram username without the @ symbol.
        limit: Maximum number of recent content items to retrieve.
        lookback_days: Only keep content published within this number of days.

    Returns:
        A list of normalized recent Instagram content items ordered
        from newest to oldest.
    """

    results = _run_apify_actor(
        POST_ACTOR,
        {
            "username": [username],
            "resultsLimit": limit,
            "dataDetailLevel": "detailedData",
            "skipPinnedPosts": True,
        },
    )
    logger.info("Content scrape: requested %s items, Apify returned %s", limit, len(results))

    normalized = [_normalize_content_item(item) for item in results]

    normalized.sort(
        key=lambda item: item.get("raw_data", {}).get("timestamp") or "",
        reverse=True,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    recent_content = []
    for item in normalized:
        timestamp = parse_timestamp(item.get("raw_data", {}).get("timestamp"))
        if timestamp is None:
            continue
        if timestamp >= cutoff:
            recent_content.append(item)

    return recent_content[:limit]


# =========================================================
# STEP 3 — SCRAPE DETAILS FOR THE REELS IN THAT WINDOW
# =========================================================


def enrich_reels_for_recent_content(recent_content: list[dict]) -> list[dict]:
    """
    Enrich ONLY Reel items already present in recent_content.

    Instead of scraping the restaurant's whole Reel feed, this function:
    1. Identifies Reels inside recent_content.
    2. Builds direct Reel URLs.
    3. Sends only those Reel URLs to the Apify Reel scraper.
    4. Matches the returned Reel data back to the original content items.

    Non-Reel posts remain unchanged.
    """

    if not recent_content:
        return []

    content_models = [ScrapedContent.model_validate(item) for item in recent_content]

    # 1-2. Identify ONLY Reels already inside recent_content and build their URLs.
    reel_urls: list[str] = []

    for item_model in content_models:
        product_type = (item_model.raw_data.product_type or "").strip().lower()
        content_url = (item_model.raw_data.content_url or "").strip()

        # Instagram/Apify commonly labels Reels as "clips".
        is_reel = (
            product_type in {"clips", "clip", "reel", "reels"}
            or "/reel/" in content_url.lower()
            or "/reels/" in content_url.lower()
        )
        if not is_reel:
            continue

        # Prefer the existing direct Reel URL, otherwise build it from the shortcode.
        if "/reel/" in content_url.lower() or "/reels/" in content_url.lower():
            reel_url = content_url
        elif item_model.short_code:
            reel_url = f"https://www.instagram.com/reel/{item_model.short_code}/"
        else:
            # Cannot target this Reel directly.
            continue

        if reel_url not in reel_urls:
            reel_urls.append(reel_url)

    # No Reels in the selected content window.
    if not reel_urls:
        return [item_model.model_dump() for item_model in content_models]

    logger.info(
        "Found %s Reel(s) inside %s recent content items.",
        len(reel_urls),
        len(content_models),
    )

    # 3. Scrape ONLY those exact Reels.
    reel_rows = _run_apify_actor(
        REEL_ACTOR,
        {
            "username": reel_urls,
            "skipPinnedPosts": False,
            "skipTrialReels": False,
            "includeSharesCount": False,
            "includeTranscript": True,
            "includeDownloadedVideo": False,
        },
    )

    reel_by_id: dict[str, dict] = {}
    reel_by_shortcode: dict[str, dict] = {}

    for reel in reel_rows:
        reel_id = reel.get("id")
        short_code = reel.get("shortCode") or _shortcode_from_url(reel.get("url"))

        if reel_id is not None:
            reel_by_id[str(reel_id)] = reel
        if short_code:
            reel_by_shortcode[str(short_code)] = reel

    # 4. Merge Reel details into the ORIGINAL recent content.
    enriched: list[dict] = []

    for item_model in content_models:
        match = None

        if item_model.content_id and item_model.content_id in reel_by_id:
            match = reel_by_id[item_model.content_id]
        elif item_model.short_code and item_model.short_code in reel_by_shortcode:
            match = reel_by_shortcode[item_model.short_code]

        if match:
            reel_details = _normalize_reel_details(match)
            item_model.reel_details = reel_details

            # Fill fields only when missing from the main content scraper.
            if item_model.raw_data.likes is None:
                item_model.raw_data.likes = match.get("likesCount")

            if item_model.raw_data.comments is None:
                item_model.raw_data.comments = match.get("commentsCount")

            if item_model.raw_data.views is None:
                item_model.raw_data.views = reel_details.views or reel_details.plays


            # Use the Reel thumbnail only when the main scraper gave no image.
            if not item_model.raw_data.image_urls:
                item_model.raw_data.image_urls = _extract_images(match)

        enriched.append(item_model.model_dump())

    return enriched


# =========================================================
# PART 1 ENTRY POINT
# =========================================================


def scrape_instagram_data(
    username: str,
    content_limit: int,
    lookback_days: int,
) -> ScrapedInstagramData:
    """
    Run the whole scrape for one restaurant and return the raw data.

    Profile first (required), then one recent-content window, then Reel
    details for the Reels inside that window.
    """

    scraped_at = datetime.now(timezone.utc).isoformat()

    profile = InstagramProfile.model_validate(scrape_instagram_profile(username))

    recent_content = scrape_recent_instagram_content(
        username=username,
        limit=content_limit,
        lookback_days=lookback_days,
    )
    content = enrich_reels_for_recent_content(recent_content)

    return ScrapedInstagramData(
        scraped_at=scraped_at,
        profile=profile,
        content=[ScrapedContent.model_validate(item) for item in content],
        content_limit=content_limit,
        lookback_days=lookback_days,
    )
