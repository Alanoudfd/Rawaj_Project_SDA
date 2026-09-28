import json
import os
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from statistics import median
from typing import Any

from apify_client import ApifyClient
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from .research_models import (
    AnalyzedContent,
    ContentAnalysis,
    ContentRawData,
    CountPct,
    ProfileAnalysis,
    ReelDetails,
    ResearchMetrics,
    ResearchSignal,
    ScrapedContent,
)

load_dotenv()


# =========================================================
# CONFIGURATION
# =========================================================

PROFILE_ACTOR = "apify/instagram-profile-scraper"
POST_ACTOR = "apify/instagram-post-scraper"
REEL_ACTOR = "apify/instagram-reel-scraper"



# =========================================================
# INTERNAL HELPERS (NOT EXPOSED AS AGENT TOOLS)
# =========================================================


def _get_apify_client() -> ApifyClient:
    token = os.getenv("APIFY_API_TOKEN")
    if not token:
        raise ValueError("APIFY_API_TOKEN is missing from .env")
    return ApifyClient(token)


def _get_llm() -> ChatOpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is missing from .env")
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        timeout=120,
        max_retries=3,
        use_responses_api=True,
    )


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


def _parse_timestamp(value: str | None) -> datetime | None:
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
            video_url=raw.get("videoUrl") or raw.get("video_url"),
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


def _extract_audio_info(reel: dict) -> tuple[str | None, str | None]:
    music = reel.get("musicInfo") or reel.get("music_info") or {}
    if not isinstance(music, dict):
        return None, None

    title = (
        music.get("title")
        or music.get("songName")
        or music.get("song_name")
        or music.get("audioTitle")
    )
    artist = (
        music.get("artist")
        or music.get("artistName")
        or music.get("artist_name")
    )
    return title, artist


def _normalize_reel_details(raw: dict) -> ReelDetails:
    audio_title, audio_artist = _extract_audio_info(raw)

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
        audio_title=audio_title,
        audio_artist=audio_artist,
        enrichment_success=True,
    )


def _pct(count: int, total: int) -> float:
    return round((count / total) * 100, 2) if total else 0.0


def _normalize_label(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(str(value).strip().lower().split())
    return cleaned or None


def _format_key(item: dict) -> str:
    if item.get("reel_details"):
        return "reel"

    raw = item.get("raw_data", {})
    product_type = str(raw.get("product_type") or "").lower()
    content_type = str(raw.get("content_type") or "").lower()

    if "carousel" in product_type or content_type in {"sidecar", "carousel"}:
        return "carousel"
    if content_type == "video":
        return "video"
    if content_type == "image":
        return "image"
    return content_type or product_type or "unknown"





def scrape_instagram_profile(username: str) -> dict:
    """
    Scrape the public Instagram profile for one restaurant.

    Use this first. Returns bio, followers, following, post count, website,
    business category, verification status, and account metadata.

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
# STAGE 2 — ANALYZE Resturant Instagram Profile
# =========================================================


def analyze_instagram_profile(
    profile: dict,
    known_email: str | None = None,
    known_location: str | None = None,
) -> dict:
    """
    Analyze the scraped profile/bio as research evidence.

    Use this after scrape_instagram_profile. It checks whether the bio clearly
    identifies cuisine/business, location, a CTA/value proposition, and whether
    public contact/access methods are present. It does not qualify the prospect.
    """

    structured_llm = _get_llm().with_structured_output(ProfileAnalysis, method="json_schema")

    prompt = f"""
Analyze this restaurant Instagram profile as neutral research evidence.

PROFILE:
{json.dumps(profile, ensure_ascii=False, indent=2)}

KNOWN DATABASE CONTEXT:
Email: {known_email}
Location: {known_location}

Rules:
- Understand Arabic and English naturally.
- Do not score, qualify, identify gaps, or recommend improvements.
- Report only what is supported by the profile or supplied database context.
- A profile CTA can be any meaningful next-action instruction; do not use a fixed taxonomy.
- website_available/external_link_available should reflect the scraped external URL.
- email_available may use the supplied database email.
- phone_available should be true only if a phone/WhatsApp contact is actually visible in the bio/profile evidence.
"""

    result = structured_llm.invoke(prompt)

    # Make deterministic contact fields authoritative where possible.
    result.contact_accessibility.website_available = bool(profile.get("website"))
    result.contact_accessibility.external_link_available = bool(profile.get("website"))
    result.contact_accessibility.email_available = bool(known_email)
    result.profile_completeness.has_external_link = bool(profile.get("website"))
    result.profile_completeness.has_location = (
        result.profile_completeness.has_location
        or result.bio.location_present
        or bool(known_location)
    )
    result.profile_completeness.has_contact_method = (
        result.contact_accessibility.website_available
        or result.contact_accessibility.email_available
        or result.contact_accessibility.phone_available
    )

    return result.model_dump()




# def scrape_recent_instagram_content(
#     username: str,
#     limit: int = 15,
# ) -> list[dict]:
#     """
#     Scrape the latest Instagram content window for a public restaurant profile.

#     This is ONE total content limit across the feed, not separate limits for
#     images and Reels. The returned items may include images, carousels, videos,
#     and Reels when Instagram exposes them in the profile feed.

#     Args:
#         username: Instagram username without @.
#         limit: Total number of recent content items to retrieve. Default 15.
#     """

#     results = _run_apify_actor(
#         POST_ACTOR,
#         {
#             "username": [username],
#             "resultsLimit": limit,
#             # Detailed data improves carousel/video metadata and productType.
#             "dataDetailLevel": "detailedData",
#             # Focus on the true recent timeline rather than old pinned content.
#             "skipPinnedPosts": True,
#         },
#     )

#     normalized = [_normalize_content_item(item) for item in results]
   # Sort newest first when timestamps are available.
    # normalized.sort(
    #     key=lambda item: item.get("raw_data", {}).get("timestamp") or "",
    #     reverse=True,
    # )

    # return normalized[:limit]

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
    print(f"Requested limit: {limit}")
    print(f"Apify returned: {len(results)} items")

    normalized = [
        _normalize_content_item(item)
        for item in results
    ]

    normalized.sort(
        key=lambda item:
            item.get("raw_data", {}).get("timestamp") or "",
        reverse=True,
    )

    cutoff = datetime.now(timezone.utc) - timedelta(
        days=lookback_days
    )

    recent_content = []

    for item in normalized:

        timestamp = _parse_timestamp(
            item.get("raw_data", {}).get("timestamp")
        )

        if timestamp is None:
            continue

        if timestamp >= cutoff:
            recent_content.append(item)

    return recent_content[:limit]





def enrich_reels_for_recent_content(
    username: str,
    recent_content: list[dict],
) -> list[dict]:
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

    # Keep parameter for compatibility with existing calls.
    # We no longer scrape the whole account by username.
    _ = username

    content_models: list[ScrapedContent] = [
        ScrapedContent.model_validate(item)
        for item in recent_content
    ]

    reel_urls: list[str] = []

    # ---------------------------------------------------------
    # 1. Identify ONLY Reels already inside recent_content
    # ---------------------------------------------------------
    for item_model in content_models:

        product_type = (
            item_model.raw_data.product_type or ""
        ).strip().lower()

        content_url = (
            item_model.raw_data.content_url or ""
        ).strip()

        # Instagram/Apify commonly labels Reels as "clips".
        is_reel = (
            product_type in {"clips", "clip", "reel", "reels"}
            or "/reel/" in content_url.lower()
            or "/reels/" in content_url.lower()
        )

        if not is_reel:
            continue

        # Prefer the existing direct Reel URL.
        if "/reel/" in content_url.lower() or "/reels/" in content_url.lower():
            reel_url = content_url

        # Otherwise construct the Reel URL from its shortcode.
        elif item_model.short_code:
            reel_url = (
                f"https://www.instagram.com/reel/"
                f"{item_model.short_code}/"
            )

        else:
            # Cannot target this Reel directly.
            continue

        if reel_url not in reel_urls:
            reel_urls.append(reel_url)

    # No Reels in the selected content window.
    if not reel_urls:
        return [
            item_model.model_dump()
            for item_model in content_models
        ]

    print(
        f"Found {len(reel_urls)} Reel(s) "
        f"inside {len(content_models)} recent content items."
    )

    # ---------------------------------------------------------
    # 2. Scrape ONLY those exact Reels
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # 3. Build lookup maps
    # ---------------------------------------------------------
    reel_by_id: dict[str, dict] = {}
    reel_by_shortcode: dict[str, dict] = {}

    for reel in reel_rows:

        reel_id = reel.get("id")

        short_code = (
            reel.get("shortCode")
            or _shortcode_from_url(reel.get("url"))
        )

        if reel_id is not None:
            reel_by_id[str(reel_id)] = reel

        if short_code:
            reel_by_shortcode[str(short_code)] = reel

    # ---------------------------------------------------------
    # 4. Merge Reel details into the ORIGINAL recent content
    # ---------------------------------------------------------
    enriched: list[dict] = []

    for item_model in content_models:

        match = None

        if (
            item_model.content_id
            and item_model.content_id in reel_by_id
        ):
            match = reel_by_id[item_model.content_id]

        elif (
            item_model.short_code
            and item_model.short_code in reel_by_shortcode
        ):
            match = reel_by_shortcode[item_model.short_code]

        if match:

            reel_details = _normalize_reel_details(match)

            item_model.reel_details = reel_details

            # Fill engagement fields only when missing
            # from the main content scraper.
            if item_model.raw_data.likes is None:
                item_model.raw_data.likes = match.get(
                    "likesCount"
                )

            if item_model.raw_data.comments is None:
                item_model.raw_data.comments = match.get(
                    "commentsCount"
                )

            if item_model.raw_data.views is None:
                item_model.raw_data.views = (
                    reel_details.views
                    or reel_details.plays
                )

            if not item_model.raw_data.video_url:
                item_model.raw_data.video_url = match.get(
                    "videoUrl"
                )

            # Use Reel thumbnail only when the main scraper
            # did not already provide an image.
            if not item_model.raw_data.image_urls:
                item_model.raw_data.image_urls = (
                    _extract_images(match)
                )

        enriched.append(
            item_model.model_dump()
        )

    return enriched
#

# =========================================================
# INTERNAL CONTENT ANALYZER
# =========================================================


def _analyze_single_content(item: dict) -> dict:
    content = ScrapedContent.model_validate(item)
    structured_llm = _get_llm().with_structured_output(ContentAnalysis, method="json_schema")

    transcript = None
    if content.reel_details:
        transcript = content.reel_details.transcript

    system_text = """
You are Rawaj's Instagram Content Research Analyst.
Analyze ONE restaurant content item as evidence only.

Hard rules:
- Understand Arabic and English naturally.
- Analyze every item whether it is an image, carousel, normal video, or Reel.
- Always analyze the caption and engagement metadata supplied.
- Analyze the supplied image(s)/cover image visually.
- For a matched Reel, also use its transcript when available.
- Do NOT claim you watched the full video. The model receives cover/images and transcript, not raw video frames.
- Do NOT qualify the restaurant, score it, label anything a marketing gap, or recommend a strategy.

CTA:
- There is NO predefined CTA list.
- Decide from context whether the content contains a meaningful call-to-action.
- If present, provide a short natural-language intent label and a clear description of what the audience is encouraged to do.

PROMOTION:
- There is NO predefined promotion list.
- Decide from context whether the content is promotional.
- If present, provide a short natural-language intent label and explain naturally what is being promoted.

CONTENT CATEGORIES:
- There is NO fixed content-category list.
- Infer 1-3 concise normalized labels from the actual content so they can later be aggregated.
- Keep labels semantically stable and concise, preferably lowercase snake_case.

CONTENT PILLAR:

You MUST classify the post into exactly ONE primary content pillar.

Allowed values only:

- food_product:
  Food, beverages, dishes, menu items, product showcases.

- offers_campaigns:
  Discounts, bundles, limited offers, launches, seasonal campaigns,
  special promotions.

- brand_storytelling:
  Brand identity, brand values, restaurant story, positioning,
  cuisine identity.

- entertainment_humor:
  Memes, jokes, trends, humorous or entertainment-first content.

- behind_the_scenes:
  Kitchen preparation, cooking process, operations,
  behind-the-scenes activity.

- people_staff:
  Chefs, employees, founders, team members, staff-focused content.

- dining_experience:
  Restaurant atmosphere, customer dining experience, ambiance,
  tables, restaurant environment.

- educational:
  Informative content, food education, ingredient explanations,
  cooking knowledge, cultural information.

- social_proof:
  Customer testimonials, reviews, user-generated content,
  customer reactions or endorsements.

- community_engagement:
  Questions, polls, contests, interactive community-focused content.

Select the ONE pillar that best represents the primary purpose of the post.
Do not invent another pillar.

EVIDENCE:
- Every conclusion must be grounded in caption, visual, transcript, metadata, or a combination.
- If something is unclear, do not assume it.
"""

    text_payload = {
        "content_id": content.content_id,
        "content_url": content.raw_data.content_url,
        "timestamp": content.raw_data.timestamp,
        "raw_content_type": content.raw_data.content_type,
        "product_type": content.raw_data.product_type,
        "caption": content.raw_data.caption,
        "likes": content.raw_data.likes,
        "comments": content.raw_data.comments,
        "views": content.raw_data.views,
        "hashtags": content.raw_data.hashtags,
        "alt_text": content.raw_data.alt_text,
        "reel_transcript": transcript,
        "reel_duration_seconds": (
            content.reel_details.duration_seconds if content.reel_details else None
        ),
    }

    message_content: list[dict] = [
        {
            "type": "text",
            "text": json.dumps(text_payload, ensure_ascii=False, indent=2),
        }
    ]

    for image_url in content.raw_data.image_urls[:10]:
        message_content.append(
            {
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "high"},
            }
        )

    analysis = structured_llm.invoke(
        [
            SystemMessage(content=system_text),
            HumanMessage(content=message_content),
        ]
    )

    return AnalyzedContent(
        **content.model_dump(),
        analysis=analysis,
        analysis_error=None,
    ).model_dump()


# =========================================================
# STAGE 5 — ANALYZE ALL RECENT CONTENT
# =========================================================


def analyze_instagram_content(recent_content: list[dict]) -> list[dict]:
    """
    Analyze EVERY item in the supplied recent-content window individually.

    For images/carousels: caption + actual images + engagement metadata.
    For normal videos: caption + cover/image + engagement metadata.
    For matched Reels: caption + engagement + cover/image + transcript when available.

    CTA and promotion meanings are inferred from context with no fixed taxonomy.
    One failed item does not stop analysis of the remaining items.
    """

    analyzed: list[dict] = []

    for item in recent_content:
        try:
            analyzed.append(_analyze_single_content(item))
        except Exception as exc:
            content = ScrapedContent.model_validate(item)
            analyzed.append(
                AnalyzedContent(
                    **content.model_dump(),
                    analysis=None,
                    analysis_error=str(exc),
                ).model_dump()
            )

    return analyzed


# =========================================================
# STAGE 6 — CALCULATE AGGREGATED METRICS
# =========================================================


def calculate_research_metrics(
    profile: dict,
    analyzed_content: list[dict],
) -> dict:
    """
    Calculate deterministic account-level research metrics.

    Use this after analyze_instagram_content. Calculates activity, engagement,
    media-format mix, dynamic content mix, CTA/promotion prevalence, branding,
    commerce visibility, and Reel metrics. It does not judge whether values are
    good or bad.
    """

    items = [AnalyzedContent.model_validate(item) for item in analyzed_content]
    total = len(items)
    now = datetime.now(timezone.utc)

    # ---------- Activity ----------
    dates = [
        parsed
        for parsed in (_parse_timestamp(item.raw_data.timestamp) for item in items)
        if parsed is not None
    ]

    content_last_30_days = sum(1 for date in dates if 0 <= (now - date).days <= 30)
    content_per_week = round((content_last_30_days / 30) * 7, 2)
    days_since_last_content = None
    if dates:
        days_since_last_content = max((now - max(dates)).days, 0)

    # ---------- Engagement ----------
    engagement_items = [
        item
        for item in items
        if item.raw_data.likes is not None or item.raw_data.comments is not None
    ]

    avg_likes = med_likes = avg_comments = engagement_rate = None
    if engagement_items:
        likes = [item.raw_data.likes or 0 for item in engagement_items]
        comments = [item.raw_data.comments or 0 for item in engagement_items]

        avg_likes = round(sum(likes) / len(likes), 2)
        med_likes = round(float(median(likes)), 2)
        avg_comments = round(sum(comments) / len(comments), 2)

        followers = profile.get("followers")
        if followers and followers > 0:
            engagement_rate = round(((avg_likes + avg_comments) / followers) * 100, 3)

    # ---------- Format mix ----------
    format_counter = Counter(_format_key(item.model_dump()) for item in items)
    format_mix = {
        key: CountPct(count=count, pct=_pct(count, total))
        for key, count in format_counter.items()
    }

    # ---------- Valid analyses ----------
    valid = [item for item in items if item.analysis is not None]
    valid_total = len(valid)

    # ---------- Dynamic content mix ----------
    # category_counter: Counter[str] = Counter()
    # for item in valid:
    #     for category in item.analysis.content_categories:
    #         label = _normalize_label(category)
    #         if label:
    #             category_counter[label] += 1

    # content_mix = {
    #     key: CountPct(count=count, pct=_pct(count, valid_total))
    #     for key, count in category_counter.items()
    # }
    pillar_counter: Counter[str] = Counter()
    for item in valid:
        pillar = item.analysis.content_pillar
        if pillar:
            pillar_counter[pillar] += 1

    content_mix = {
        pillar: CountPct(
            count=count,
            pct=_pct(count, valid_total),
        )
        for pillar, count in pillar_counter.items()
    }

    # ---------- CTA ----------
    cta_items = [item for item in valid if item.analysis.cta.present]
    cta_intents: Counter[str] = Counter()
    for item in cta_items:
        label = _normalize_label(item.analysis.cta.intent)
        if label:
            cta_intents[label] += 1

    # ---------- Promotion ----------
    promo_items = [item for item in valid if item.analysis.promotion.present]
    promotion_intents: Counter[str] = Counter()
    for item in promo_items:
        label = _normalize_label(item.analysis.promotion.intent)
        if label:
            promotion_intents[label] += 1

    # ---------- Visual / commerce ----------
    logo_count = sum(1 for item in valid if item.analysis.visual_signals.logo_visible)
    branding_count = sum(1 for item in valid if item.analysis.visual_signals.branding_visible)
    menu_count = sum(1 for item in valid if item.analysis.visual_signals.menu_visible)
    price_count = sum(1 for item in valid if item.analysis.visual_signals.price_visible)
    offer_count = sum(1 for item in valid if item.analysis.visual_signals.offer_visible)

    # ---------- Reel metrics ----------
    reels = [item for item in items if item.reel_details is not None]
    enriched_reels = [
        item
        for item in reels
        if item.reel_details and item.reel_details.enrichment_success
    ]

    reel_views = [
        item.reel_details.views or item.reel_details.plays or item.raw_data.views
        for item in enriched_reels
        if (
            item.reel_details.views is not None
            or item.reel_details.plays is not None
            or item.raw_data.views is not None
        )
    ]
    reel_durations = [
        item.reel_details.duration_seconds
        for item in enriched_reels
        if item.reel_details.duration_seconds is not None
    ]
    transcript_count = sum(
        1
        for item in enriched_reels
        if item.reel_details and item.reel_details.transcript
    )

    metrics = ResearchMetrics.model_validate(
        {
            "activity": {
                "content_last_30_days": content_last_30_days,
                "content_per_week": content_per_week,
                "days_since_last_content": days_since_last_content,
            },
            "engagement": {
                "average_likes": avg_likes,
                "median_likes": med_likes,
                "average_comments": avg_comments,
                "engagement_rate_pct": engagement_rate,
                "sample_size": len(engagement_items),
            },
            "format_mix": {
                key: value.model_dump() for key, value in format_mix.items()
            },
            "content_mix": {
                key: value.model_dump() for key, value in content_mix.items()
            },
            "cta": {
                "content_with_cta": len(cta_items),
                "any_cta_pct": _pct(len(cta_items), valid_total),
                "cta_intents": dict(cta_intents),
            },
            "promotion": {
                "promotional_content": len(promo_items),
                "promotional_content_pct": _pct(len(promo_items), valid_total),
                "promotion_intents": dict(promotion_intents),
            },
            "branding": {
                "logo_presence_pct": _pct(logo_count, valid_total),
                "branding_presence_pct": _pct(branding_count, valid_total),
            },
            "commerce_visibility": {
                "menu_visible_pct": _pct(menu_count, valid_total),
                "price_visible_pct": _pct(price_count, valid_total),
                "offer_visible_pct": _pct(offer_count, valid_total),
            },
            "reels": {
                "reels_detected": len(reels),
                "reels_enriched": len(enriched_reels),
                "reel_content_pct": _pct(len(reels), total),
                "average_views": (
                    round(sum(reel_views) / len(reel_views), 2) if reel_views else None
                ),
                "median_views": round(float(median(reel_views)), 2) if reel_views else None,
                "average_duration_seconds": (
                    round(sum(reel_durations) / len(reel_durations), 2)
                    if reel_durations
                    else None
                ),
                "transcript_available_pct": _pct(transcript_count, len(enriched_reels)),
            },
        }
    )

    return metrics.model_dump()


# =========================================================
# STAGE 7 — BUILD EVIDENCE-BACKED RESEARCH SIGNALS
# =========================================================


def build_research_signals(
    metrics: dict,
    analyzed_content: list[dict],
) -> list[dict]:
    """
    Build compact, evidence-backed observations for the Qualification Agent.

    Signals are descriptive only. They must not label the account good/bad,
    strong/weak, qualified/unqualified, or recommend any action.
    """

    m = ResearchMetrics.model_validate(metrics)
    items = [AnalyzedContent.model_validate(item) for item in analyzed_content]

    def ids_where(predicate) -> list[str]:
        return [
            item.content_id
            for item in items
            if item.content_id and item.analysis is not None and predicate(item)
        ]

    signals: list[ResearchSignal] = []

    signals.append(
        ResearchSignal(
            signal_id="activity_01",
            dimension="posting_activity",
            observation=(
                f"Observed {m.activity.content_last_30_days} content items in the last 30 days "
                f"({m.activity.content_per_week} per week in the observed window); "
                f"days since latest content: {m.activity.days_since_last_content}."
            ),
            metric_path="metrics.activity",
            value=m.activity.model_dump(),
            confidence=1.0,
        )
    )

    signals.append(
        ResearchSignal(
            signal_id="engagement_01",
            dimension="engagement",
            observation=(
                f"Across {m.engagement.sample_size} items with engagement data, average likes were "
                f"{m.engagement.average_likes}, median likes {m.engagement.median_likes}, "
                f"average comments {m.engagement.average_comments}, and follower-normalized "
                f"engagement rate was {m.engagement.engagement_rate_pct}%."
            ),
            metric_path="metrics.engagement",
            value=m.engagement.model_dump(),
            confidence=1.0,
        )
    )

    cta_ids = ids_where(lambda item: item.analysis.cta.present)
    signals.append(
        ResearchSignal(
            signal_id="cta_01",
            dimension="cta_usage",
            observation=(
                f"CTA detected in {m.cta.content_with_cta} analyzed content items "
                f"({m.cta.any_cta_pct}%). Observed intent labels: {dict(m.cta.cta_intents)}."
            ),
            metric_path="metrics.cta",
            value=m.cta.model_dump(),
            evidence_content_ids=cta_ids,
            confidence=0.9,
        )
    )

    promo_ids = ids_where(lambda item: item.analysis.promotion.present)
    signals.append(
        ResearchSignal(
            signal_id="promotion_01",
            dimension="promotional_activity",
            observation=(
                f"Promotional intent detected in {m.promotion.promotional_content} analyzed content "
                f"items ({m.promotion.promotional_content_pct}%). Observed promotion intent labels: "
                f"{dict(m.promotion.promotion_intents)}."
            ),
            metric_path="metrics.promotion",
            value=m.promotion.model_dump(),
            evidence_content_ids=promo_ids,
            confidence=0.9,
        )
    )

    commerce_ids = ids_where(
        lambda item: (
            item.analysis.visual_signals.menu_visible
            or item.analysis.visual_signals.price_visible
            or item.analysis.visual_signals.offer_visible
        )
    )
    signals.append(
        ResearchSignal(
            signal_id="commerce_01",
            dimension="commerce_visibility",
            observation=(
                f"Within analyzed visuals: menu visible in {m.commerce_visibility.menu_visible_pct}%, "
                f"price visible in {m.commerce_visibility.price_visible_pct}%, and offer messaging "
                f"visible in {m.commerce_visibility.offer_visible_pct}% of items."
            ),
            metric_path="metrics.commerce_visibility",
            value=m.commerce_visibility.model_dump(),
            evidence_content_ids=commerce_ids,
            confidence=0.9,
        )
    )

    branding_ids = ids_where(
        lambda item: (
            item.analysis.visual_signals.logo_visible
            or item.analysis.visual_signals.branding_visible
        )
    )
    signals.append(
        ResearchSignal(
            signal_id="branding_01",
            dimension="branding_presence",
            observation=(
                f"Logo was visually detected in {m.branding.logo_presence_pct}% of analyzed items; "
                f"recognizable branding was detected in {m.branding.branding_presence_pct}%."
            ),
            metric_path="metrics.branding",
            value=m.branding.model_dump(),
            evidence_content_ids=branding_ids,
            confidence=0.9,
        )
    )

    if m.reels.reels_detected > 0:
        reel_ids = [
            item.content_id
            for item in items
            if item.content_id and item.reel_details is not None
        ]
        signals.append(
            ResearchSignal(
                signal_id="reels_01",
                dimension="reel_activity",
                observation=(
                    f"{m.reels.reels_detected} of the observed content items were matched as Reels "
                    f"({m.reels.reel_content_pct}% of the content window). {m.reels.reels_enriched} "
                    f"were enriched; average Reel views: {m.reels.average_views}; transcript "
                    f"availability: {m.reels.transcript_available_pct}%."
                ),
                metric_path="metrics.reels",
                value=m.reels.model_dump(),
                evidence_content_ids=reel_ids,
                confidence=1.0,
            )
        )

    return [signal.model_dump() for signal in signals]

# %%
