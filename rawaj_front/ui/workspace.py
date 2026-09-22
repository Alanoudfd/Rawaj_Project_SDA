"""Streamlit Post Workspace for turning a chosen Rawaj idea into an executable Instagram post.

The page has four responsibilities only:
1. Ask for the minimum facts the chosen idea needs.
2. Generate an actionable Post Kit (format + execution guide + copy).
3. Let the owner preview/upload the required assets.
4. Hand the finished kit to Instagram and record completion.

All reusable logic lives in ``ui.post_kit``; all database/model work stays behind
``ui.api``.  Keeping those boundaries prevents this page from becoming another
business-logic module.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from datetime import date
from html import escape

import streamlit as st

from ui import api
from ui import post_kit as kitlib
from ui.icons import icon
from ui.plan import progress

TONE_LABELS = {code: label for label, code in kitlib.TONES.items()}


@dataclass(frozen=True)
class WorkspaceContext:
    restaurant: dict
    plan: dict
    task: dict
    idea: dict
    wid: str
    restaurant_name: str
    when: str


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------


def keep(key: str, value) -> None:
    """Initialize a widget once; Streamlit removes widget values when pages change."""
    if key not in st.session_state:
        st.session_state[key] = value


def chip(state: str, text: str) -> str:
    symbol = {"ok": "check", "na": "info"}.get(state, "alert")
    return f'<span class="chk {state}">{icon(symbol, 13, 2.2)}{escape(text)}</span>'


def _workspace_id(restaurant: dict, task: dict, idea: dict) -> str:
    idea_key = zlib.crc32(str(idea.get("name", "idea")).encode("utf-8"))
    return f"{restaurant['id']}_{task['id']}_{idea_key}"


def _new_workspace(restaurant: dict) -> dict:
    return {
        "facts": kitlib.default_facts(restaurant),
        "facts_plan": None,
        "seed_rows": [],
        "row_count": 0,
        "resp": None,
        "generated_for": None,
        "caption": "",
        "tone": "warm",
        "overlay": "",
        "checked": {},
        "assets": {},
        "upload_generation": 0,
        "scheduled": False,
        "before": None,
        "error": "",
    }


def _get_workspace(ctx: WorkspaceContext) -> dict:
    ws = st.session_state.setdefault("post_workspaces", {}).setdefault(
        ctx.wid, _new_workspace(ctx.restaurant)
    )
    for key, value in _new_workspace(ctx.restaurant).items():
        ws.setdefault(key, value)

    # Smooth migration from the previous one-file upload state.
    legacy_media = ws.pop("media", None)
    if legacy_media and not ws["assets"]:
        ws["assets"]["final"] = legacy_media
    return ws


def _fact_key(ctx: WorkspaceContext, field: str) -> str:
    return f"fact_{ctx.wid}_{field}"


def _current_signature(ws: dict) -> str:
    return kitlib.facts_signature(ws["facts"])


def _kit_is_stale(ws: dict) -> bool:
    return bool(ws.get("resp") and ws.get("generated_for") != _current_signature(ws))


# ---------------------------------------------------------------------------
# API actions
# ---------------------------------------------------------------------------


def _ensure_facts_plan(ctx: WorkspaceContext, ws: dict) -> dict:
    if ws["facts_plan"] is not None:
        return ws["facts_plan"]

    try:
        with st.spinner("Reading the idea to see what needs to be confirmed..."):
            ws["facts_plan"] = api.facts_plan(
                ctx.restaurant["id"], ctx.task["day"], ctx.idea
            )
    except api.ApiError:
        ws["facts_plan"] = kitlib.generic_plan()

    ws["seed_rows"] = kitlib.starting_rows(ws["facts_plan"], ctx.restaurant)
    ws["row_count"] = len(ws["seed_rows"])
    return ws["facts_plan"]


def _generate_kit(ctx: WorkspaceContext, ws: dict) -> bool:
    try:
        with st.spinner("Building the posting guide and checking every claim..."):
            response = api.create_post_kit(
                ctx.restaurant["id"],
                ctx.task["day"],
                ctx.idea,
                ws["facts"],
                ws["tone"],
            )
    except api.ApiError as exc:
        ws["error"] = exc.detail or str(exc)
        return False

    ws["resp"] = response
    ws["generated_for"] = _current_signature(ws)
    ws["error"] = ""
    ws["checked"] = {}

    fresh = response["kit"]
    ws["caption"] = fresh["caption"]["text"]
    ws["overlay"] = fresh["visual"].get("text_overlay") or ""
    st.session_state[f"cap_{ctx.wid}"] = ws["caption"]
    st.session_state[f"overlay_{ctx.wid}"] = ws["overlay"]

    for key in list(st.session_state):
        if str(key).startswith(f"chk_{ctx.wid}_"):
            del st.session_state[key]
    return True


def _rewrite_caption(ctx: WorkspaceContext, ws: dict, change: str) -> bool:
    current = st.session_state.get(f"cap_{ctx.wid}", ws["caption"])
    try:
        with st.spinner("Rewriting your caption..."):
            rewritten = api.rewrite_caption(
                ctx.restaurant["id"],
                ctx.task["day"],
                current,
                change,
                ws["facts"],
                ctx.idea["content_format"],
            )
    except api.ApiError as exc:
        st.error(exc.detail or str(exc))
        return False

    ws["caption"] = rewritten["text"]
    st.session_state[f"cap_{ctx.wid}"] = rewritten["text"]
    return True


# ---------------------------------------------------------------------------
# Header cards
# ---------------------------------------------------------------------------


def _assets_ready(ws: dict) -> bool:
    resp = ws.get("resp")
    if not resp:
        return False
    shoot = resp["kit"]["shoot"]
    fmt = shoot["format"]
    if fmt in {"carousel", "story"}:
        required = len(shoot.get("shots") or [])
        return required > 0 and all(str(i) in ws["assets"] for i in range(required))
    return "final" in ws["assets"]


def _render_progress(ctx: WorkspaceContext, ws: dict, stats: dict, posted: bool) -> None:
    done = [
        True,
        ws.get("resp") is not None and not _kit_is_stale(ws),
        _assets_ready(ws),
        ws.get("scheduled", False) or posted,
        posted,
        False,
    ]
    with st.container(key="card_steps"):
        st.markdown(
            f"""
            <div class="card-head"><h3 class="card-title">Your post, step by step</h3>
            <span class="muted">{escape(ctx.idea['name'])}</span></div>
            {kitlib.steps_html(done, confirmed=posted)}
            <p class="steps-note">Rawaj prepares the content and guide; you still publish it in Instagram.
            When the post is live, “Mark as posted” completes the calendar day.</p>
            """,
            unsafe_allow_html=True,
        )


def _render_why(ctx: WorkspaceContext) -> None:
    gap = kitlib.pick_gap(ctx.plan, ctx.task, ctx.idea)
    if gap:
        detail = (
            f" · {escape(gap['highlight_label'] or 'Evidence')}: {escape(gap['highlight'])}"
            if gap.get("highlight") else ""
        )
        reason = (
            f"This post answers a gap Rawaj found: <b>{escape(gap['gap'])}</b> "
            f"({escape(gap.get('severity') or 'unrated')}{detail}). "
            f"{escape(gap.get('key_point') or '')}"
        )
    else:
        targets = ctx.plan.get("targets") or []
        goal = targets[0] if targets else ctx.plan.get("focus", "your content plan")
        reason = f"This post supports your plan: <b>{escape(str(goal))}</b>."

    with st.container(key="card_why"):
        st.markdown(
            f"""
            <div class="why"><div class="badge">{icon('target', 20)}</div>
              <div><div class="eyebrow">Why this post</div><p>{reason}</p></div></div>
            """,
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Facts form
# ---------------------------------------------------------------------------


def _render_item_rows(ctx: WorkspaceContext, ws: dict, plan_facts: dict, language: str) -> list[dict]:
    if not plan_facts.get("items_max"):
        return []

    st.markdown(
        f'<div class="dl"><small>{escape(plan_facts["items_label"])}</small></div>',
        unsafe_allow_html=True,
    )

    items: list[dict] = []
    groups = list(plan_facts.get("suggested_groups") or [])

    for i in range(ws["row_count"]):
        seed = ws["seed_rows"][i] if i < len(ws["seed_rows"]) else {}
        for field in ("name_en", "name_ar", "price", "group"):
            keep(_fact_key(ctx, f"{field}{i}"), seed.get(field, ""))

        group = str(st.session_state[_fact_key(ctx, f"group{i}")] or "").strip()
        if plan_facts.get("wants_groups"):
            if group:
                st.markdown(
                    f'<div class="hook-card" style="margin:.65rem 0 .35rem;"><small>Moment {i + 1}</small><b>{escape(group)}</b></div>',
                    unsafe_allow_html=True,
                )
            elif groups:
                group = st.selectbox(
                    "Moment",
                    groups,
                    key=_fact_key(ctx, f"group_select{i}"),
                )
                st.session_state[_fact_key(ctx, f"group{i}")] = group

        columns = []
        if language in {"English", "Bilingual"}:
            columns.append("en")
        if language in {"Arabic", "Bilingual"}:
            columns.append("ar")
        if plan_facts.get("wants_prices"):
            columns.append("price")

        widths = [1.5 if field != "price" else 0.8 for field in columns]
        cells = iter(st.columns(widths or [1]))

        name_en = str(st.session_state[_fact_key(ctx, f"name_en{i}")] or "")
        name_ar = str(st.session_state[_fact_key(ctx, f"name_ar{i}")] or "")
        price = str(st.session_state[_fact_key(ctx, f"price{i}")] or "")

        if "en" in columns:
            name_en = next(cells).text_input(
                "Item name (English)",
                key=_fact_key(ctx, f"name_en{i}"),
                max_chars=120,
                placeholder="e.g. Spanish Latte",
            )
        if "ar" in columns:
            name_ar = next(cells).text_input(
                "اسم الصنف (العربية)",
                key=_fact_key(ctx, f"name_ar{i}"),
                max_chars=120,
                placeholder="مثال: سبانش لاتيه",
            )
        if "price" in columns:
            price = next(cells).text_input(
                "Price",
                key=_fact_key(ctx, f"price{i}"),
                max_chars=40,
                placeholder="e.g. 24 SAR",
            )

        items.append({
            "name_en": name_en.strip(),
            "name_ar": name_ar.strip(),
            "price": price.strip(),
            "group": group,
        })

    add_col, drop_col, _ = st.columns([1, 1, 2.4])
    if add_col.button(
        "Add another",
        icon=":material/add:",
        type="tertiary",
        key=f"add_{ctx.wid}",
        disabled=ws["row_count"] >= int(plan_facts["items_max"]),
    ):
        ws["row_count"] += 1
        st.rerun()

    minimum_rows = max(int(plan_facts.get("items_min") or 0), len(groups) if plan_facts.get("wants_groups") else 0)
    if drop_col.button(
        "Remove last",
        icon=":material/remove:",
        type="tertiary",
        key=f"drop_{ctx.wid}",
        disabled=ws["row_count"] <= minimum_rows,
    ):
        ws["row_count"] -= 1
        st.rerun()

    return items


def _render_facts(ctx: WorkspaceContext, ws: dict) -> None:
    plan_facts = _ensure_facts_plan(ctx, ws)
    facts = ws["facts"]

    with st.container(key="card_facts"):
        st.markdown(
            f"""
            <div class="eyebrow" style="color:var(--blue);">Confirm only what Rawaj cannot safely know</div>
            <h2 style="font:600 22px var(--head); margin:.4rem 0 .3rem;">Make this idea real.</h2>
            <p class="muted" style="margin:0 0 .8rem;">{escape(plan_facts['summary'])}
            Rawaj will create the hook, slide order, visual direction, caption and CTA.</p>
            """,
            unsafe_allow_html=True,
        )

        keep(_fact_key(ctx, "language"), facts["language"])
        language = st.radio(
            "Caption language",
            kitlib.LANGUAGES,
            horizontal=True,
            key=_fact_key(ctx, "language"),
        )

        items = _render_item_rows(ctx, ws, plan_facts, language)

        channels: list[str] = []
        if plan_facts.get("wants_channels"):
            initial_channels = facts["channels"] or plan_facts.get("suggested_channels") or []
            keep(_fact_key(ctx, "channels"), initial_channels)
            options = kitlib.DELIVERY_CHOICES + [
                c for c in plan_facts.get("suggested_channels") or []
                if c not in kitlib.DELIVERY_CHOICES
            ]
            channels = st.multiselect(
                "How can guests get it?",
                options,
                key=_fact_key(ctx, "channels"),
                accept_new_options=True,
                placeholder="Choose only the ways that are true",
            )

        offer = ""
        if plan_facts.get("wants_offer"):
            keep(_fact_key(ctx, "offer"), facts["offer"])
            offer = st.text_input(
                "Confirmed offer",
                key=_fact_key(ctx, "offer"),
                max_chars=200,
                placeholder="Only if this idea depends on a real current offer",
            )

        notes = ""
        if plan_facts.get("notes_prompt"):
            keep(_fact_key(ctx, "notes"), facts["notes"])
            notes = st.text_area(
                plan_facts["notes_prompt"],
                key=_fact_key(ctx, "notes"),
                max_chars=400,
                height=80,
                placeholder="Only confirmed information. Leave empty if there is nothing else.",
            )

        keep(_fact_key(ctx, "photo"), "Yes" if facts["has_photo"] else "No")
        has_photo = st.radio(
            "Do you already have photos/video you may use?",
            ["Yes", "No"],
            horizontal=True,
            key=_fact_key(ctx, "photo"),
        )

        ws["facts"] = {
            "items": items,
            "channels": channels,
            "offer": offer.strip(),
            "notes": notes.strip(),
            "language": language,
            "has_photo": has_photo == "Yes",
            "brand_colors": facts.get("brand_colors") or [],
        }

        missing = kitlib.missing_item_count(plan_facts, items)
        if language == "Bilingual":
            incomplete = [i for i in items if (i.get("name_en") or i.get("name_ar")) and not (i.get("name_en") and i.get("name_ar"))]
            if incomplete:
                st.markdown(
                    '<p class="hint">For a bilingual caption, add both Arabic and English names when you need the item named in both languages.</p>',
                    unsafe_allow_html=True,
                )
        if missing:
            st.markdown(
                f'<p class="hint">Add {missing} more confirmed item{"s" if missing != 1 else ""} to complete this idea.</p>',
                unsafe_allow_html=True,
            )

        if plan_facts.get("fallback"):
            st.markdown(
                '<p class="hint">Rawaj could not make an idea-specific form, so this is the safe fallback.</p>',
                unsafe_allow_html=True,
            )
            if st.button("Read the idea again", type="tertiary", key=f"replan_{ctx.wid}", icon=":material/refresh:"):
                ws["facts_plan"] = None
                ws["seed_rows"] = []
                ws["row_count"] = 0
                st.rerun()

        stale = _kit_is_stale(ws)
        if stale:
            st.warning("You changed the confirmed facts. Update the posting guide before using the old caption or instructions.")

        action, note = st.columns([1.25, 2.1], vertical_alignment="center")
        label = "Update posting guide" if ws.get("resp") else "Create posting guide"
        if action.button(
            label,
            icon=":material/auto_awesome:",
            type="primary",
            key=f"generate_{ctx.wid}",
            disabled=missing > 0,
        ):
            if _generate_kit(ctx, ws):
                st.rerun()

        note.markdown(
            '<span class="muted" style="font-size:10.5px;">Rawaj chooses the execution format and tells you exactly what to create.</span>',
            unsafe_allow_html=True,
        )
        if ws["error"]:
            st.error(ws["error"])


# ---------------------------------------------------------------------------
# Generated kit
# ---------------------------------------------------------------------------


def _render_kit_notes(resp: dict) -> None:
    notes = [
        f"Check this before you post: “{claim['text']}”. {claim['reason']}"
        for claim in resp.get("unsupported_claims") or []
    ]
    notes += [check["message"] for check in resp.get("checks") or [] if not check.get("ok")]
    if not resp.get("claims_checked", False):
        notes.append("The claim checker was unavailable. Read the public copy against your confirmed facts before posting.")

    for text in notes:
        st.markdown(
            f'<div class="flag">{icon("alert", 15)}<span>{escape(text)}</span></div>',
            unsafe_allow_html=True,
        )
    if not notes:
        st.markdown(
            f'<div class="flag good">{icon("check", 15, 2.4)}<span>Checked against the facts you confirmed.</span></div>',
            unsafe_allow_html=True,
        )


def _render_execution_summary(resp: dict) -> None:
    kit = resp["kit"]
    execution = kit.get("execution") or {}
    shoot = kit["shoot"]
    st.markdown(
        f"""
        <div class="readout">
          <small>Recommended execution · {escape(kitlib.format_name(shoot['format']))}</small>
          <b>{escape(execution.get('what_to_make') or '')}</b>
          <span>{escape(shoot.get('format_reason') or '')}</span>
        </div>
        <div class="readout" style="margin-top:.55rem;">
          <small>Start here</small>
          {escape(execution.get('owner_action') or '')}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_caption_tab(ctx: WorkspaceContext, ws: dict, resp: dict) -> None:
    kit = resp["kit"]
    cutoff = resp.get("more_cutoff", kitlib.MORE_CUTOFF)

    keep(f"tone_{ctx.wid}", TONE_LABELS[ws["tone"]])
    st.markdown('<div class="dl"><small>Choose a tone</small></div>', unsafe_allow_html=True)
    selected = st.segmented_control(
        "Tone",
        list(kitlib.TONES),
        key=f"tone_{ctx.wid}",
        label_visibility="collapsed",
    )
    if selected and kitlib.TONES[selected] != ws["tone"]:
        old_label = TONE_LABELS[ws["tone"]]
        new_tone = kitlib.TONES[selected]
        if _rewrite_caption(ctx, ws, new_tone):
            ws["tone"] = new_tone
            st.rerun()
        st.session_state[f"tone_{ctx.wid}"] = old_label

    st.markdown(
        f'<p class="hint" style="margin-top:.2rem;">{escape(kitlib.TONE_NOTES[ws["tone"]])}</p>',
        unsafe_allow_html=True,
    )

    keep(f"cap_{ctx.wid}", ws["caption"])
    length = len(st.session_state[f"cap_{ctx.wid}"])
    st.markdown(
        f'<div class="cap-head"><b>Edit caption</b><span>{length} characters</span></div>',
        unsafe_allow_html=True,
    )
    text = st.text_area(
        "Edit caption",
        key=f"cap_{ctx.wid}",
        height=200,
        label_visibility="collapsed",
    )
    ws["caption"] = text
    state, message = kitlib.subject_check(
        text,
        ws["facts"],
        cutoff,
        ctx.idea["content_format"] == "Story",
    )
    st.markdown(chip(state, message), unsafe_allow_html=True)

    choice = st.pills(
        "Change one thing",
        list(kitlib.CHIPS),
        selection_mode="single",
        key=f"rw_{ctx.wid}",
    )
    if choice:
        st.session_state[f"rw_{ctx.wid}"] = None
        if _rewrite_caption(ctx, ws, kitlib.CHIPS[choice]):
            st.rerun()

    st.markdown('<div class="dl" style="margin-top:.8rem;"><small>Hashtags</small></div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="tags">' + "".join(
            f'<span class="tag" dir="auto">{escape(tag)}</span>' for tag in kit["hashtags"]
        ) + "</div>",
        unsafe_allow_html=True,
    )
    st.code(kitlib.hashtag_text(kit["hashtags"]), language=None)


def _render_execution_tab(ctx: WorkspaceContext, ws: dict, resp: dict) -> None:
    guide = resp["kit"]["shoot"]
    duration = f" · {guide['duration_seconds']} seconds" if guide.get("duration_seconds") else ""
    st.markdown(
        f'<span class="chip">{icon("video" if guide["format"] in ("reel", "story") else "camera", 13)}'
        f'{escape(kitlib.format_name(guide["format"]))}{duration}</span>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p class="hint" style="margin-top:.5rem;"><b>Why this format:</b> {escape(guide.get("format_reason") or "")}</p>',
        unsafe_allow_html=True,
    )
    if guide.get("hook"):
        st.markdown(
            f'<div class="hook-card" style="margin-top:.8rem;"><small>Hook · first two seconds</small><b>{escape(guide["hook"])}</b></div>',
            unsafe_allow_html=True,
        )

    cards = "".join(
        kitlib.shot_card(number, shot)
        for number, shot in enumerate(guide.get("shots") or [], 1)
    )
    st.markdown(f'<div style="margin-top:.8rem;">{cards}</div>', unsafe_allow_html=True)

    st.markdown('<div class="dl"><small>Before you shoot</small></div>', unsafe_allow_html=True)
    for i, item in enumerate(guide.get("checklist") or []):
        keep(f"chk_{ctx.wid}_{i}", ws["checked"].get(i, False))
        ws["checked"][i] = st.checkbox(item, key=f"chk_{ctx.wid}_{i}")


def _render_look_tab(ctx: WorkspaceContext, ws: dict, resp: dict) -> None:
    visual = resp["kit"]["visual"]
    st.markdown(
        f"""
        <div class="dl"><small>Cover frame</small><p>{escape(visual['cover_frame'])}</p></div>
        <div class="dl"><small>The look</small><p>{escape(visual['look_notes'])}</p></div>
        """,
        unsafe_allow_html=True,
    )

    keep(f"overlay_{ctx.wid}", ws["overlay"])
    ws["overlay"] = st.text_input(
        "Cover text (optional)",
        key=f"overlay_{ctx.wid}",
        max_chars=60,
        help="Only the cover/first frame. Per-slide text is in the execution guide.",
    )
    if visual.get("overlay_placement") and ws["overlay"].strip():
        st.markdown(
            f'<p class="hint">{escape(visual["overlay_placement"])}</p>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="dl" style="margin-top:.9rem;"><small>Brand colours</small></div>', unsafe_allow_html=True)
    facts = ws["facts"]
    keep(f"colours_{ctx.wid}", bool(facts.get("brand_colors")))
    if st.toggle("Add my brand colours to the brief", key=f"colours_{ctx.wid}"):
        saved = list(facts.get("brand_colors") or []) + ["#1F2937", "#E5E7EB"]
        first, second = st.columns(2)
        keep(f"colour1_{ctx.wid}", saved[0])
        keep(f"colour2_{ctx.wid}", saved[1])
        facts["brand_colors"] = [
            first.color_picker("Main colour", key=f"colour1_{ctx.wid}"),
            second.color_picker("Accent colour", key=f"colour2_{ctx.wid}"),
        ]
    else:
        facts["brand_colors"] = []
        st.markdown(
            '<p class="hint">Rawaj does not guess brand colours.</p>',
            unsafe_allow_html=True,
        )

    rules = "".join(f"<li>{escape(rule)}</li>" for rule in resp.get("crop_rules") or [])
    st.markdown(
        f'<div class="dl" style="margin-top:.9rem;"><small>Crop rules</small><ul class="ev">{rules}</ul></div>',
        unsafe_allow_html=True,
    )


def _render_publish_tab(ctx: WorkspaceContext, resp: dict) -> None:
    kit = resp["kit"]
    headline, detail, text = kitlib.best_time_summary(
        resp["best_time"],
        ctx.when,
        passed=ctx.task["date"] < date.today(),
    )
    st.markdown(
        f"""
        <div class="time">{icon('clock', 26)}<div>
          <div class="big">{escape(headline)}</div><p><b>{escape(detail)}</b></p><p>{escape(text)}</p></div></div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown('<div class="dl" style="margin-top:1rem;"><small>Location tag</small></div>', unsafe_allow_html=True)
    st.code(kit["location_tag"], language=None)

    if kit.get("mentions"):
        rows = "".join(
            f"<li><b>{escape(m['handle'] and '@' + m['handle'].lstrip('@') or m['who'])}</b> · {escape(m['why'])}"
            f"{'' if m['handle'] else ' (add their handle)'}</li>"
            for m in kit["mentions"]
        )
        st.markdown(
            f'<div class="dl" style="margin-top:.6rem;"><small>Suggested mentions</small><ul class="ev">{rows}</ul></div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="dl" style="margin-top:.6rem;"><small>Follow-up ideas</small></div>', unsafe_allow_html=True)
    for item in kit.get("follow_ups") or []:
        options = "".join(
            f'<div class="opt" dir="auto">{escape(option)}</div>' for option in item.get("options") or []
        ) or '<div class="opt">Type something…</div>'
        sticker = (
            f'<div class="poll"><div class="q" dir="auto">{escape(item.get("sticker_text") or "")}</div>{options}</div>'
            if item.get("sticker") in {"poll", "quiz", "question"} and item.get("sticker_text")
            else ""
        )
        st.markdown(
            f'<div class="fu"><div><b>{escape(item["format"])} · {escape(item["title"])}</b>'
            f'<p>{escape(item["description"])}</p><p><b style="font-size:11px;">{escape(item["timing"])}</b></p>'
            f'</div><div>{sticker}</div></div>',
            unsafe_allow_html=True,
        )


def _render_kit(ctx: WorkspaceContext, ws: dict) -> None:
    resp = ws["resp"]
    if not resp:
        return

    with st.container(key="card_kit"):
        st.markdown(
            """
            <div class="eyebrow" style="color:var(--blue);">Your posting guide</div>
            <h2 style="font:600 22px var(--head); margin:.4rem 0 .6rem;">What to post, and exactly how to make it.</h2>
            """,
            unsafe_allow_html=True,
        )
        _render_kit_notes(resp)
        _render_execution_summary(resp)

        tab_caption, tab_execute, tab_look, tab_publish = st.tabs(
            ["Caption", "Create it", "Look", "Publish"]
        )
        with tab_caption:
            _render_caption_tab(ctx, ws, resp)
        with tab_execute:
            _render_execution_tab(ctx, ws, resp)
        with tab_look:
            _render_look_tab(ctx, ws, resp)
        with tab_publish:
            _render_publish_tab(ctx, resp)


# ---------------------------------------------------------------------------
# Preview and media uploads
# ---------------------------------------------------------------------------


def _asset_slots(resp: dict | None) -> list[tuple[str, str, str]]:
    """Return (storage_key, label, accepted_kind) for content the owner may upload."""
    if not resp:
        return [("final", "Post asset", "image_or_video")]

    shoot = resp["kit"]["shoot"]
    fmt = shoot["format"]
    shots = shoot.get("shots") or []
    if fmt == "carousel":
        return [(str(i), shot["title"], "image") for i, shot in enumerate(shots)]
    if fmt == "story":
        return [(str(i), shot["title"], "image_or_video") for i, shot in enumerate(shots)]
    if fmt == "reel":
        return [("final", "Final edited Reel", "video")]
    return [("final", "Final post image", "image")]


def _read_upload(upload, content_format: str) -> dict:
    data = upload.getvalue()
    is_video = (upload.type or "").startswith("video/") or upload.name.lower().endswith((".mp4", ".mov"))
    if is_video:
        return {"name": upload.name, "kind": "video", "bytes": data}

    check = kitlib.photo_check(data, content_format)
    return {
        "name": upload.name,
        "kind": "image",
        "bytes": data,
        "check": check,
        "preview": check["preview"],
    }


def _render_preview(ctx: WorkspaceContext, ws: dict) -> None:
    resp = ws.get("resp")
    kit = resp["kit"] if resp else None
    actual_format = kitlib.execution_format(resp, ctx.idea["content_format"])
    cutoff = resp.get("more_cutoff", kitlib.MORE_CUTOFF) if resp else kitlib.MORE_CUTOFF
    slots = _asset_slots(resp)

    preview_index = 0
    if len(slots) > 1:
        preview_index = st.selectbox(
            "Preview",
            list(range(len(slots))),
            format_func=lambda i: f"{i + 1}. {slots[i][1]}",
            key=f"preview_asset_{ctx.wid}",
            label_visibility="collapsed",
        )

    storage_key = slots[preview_index][0]
    media = ws["assets"].get(storage_key)
    overlay = ws["overlay"]
    if kit and preview_index > 0 and preview_index < len(kit["shoot"].get("shots") or []):
        overlay = kit["shoot"]["shots"][preview_index].get("overlay_text") or ""

    st.markdown(
        kitlib.preview_html(
            handle=ctx.restaurant.get("instagram_username") or ctx.restaurant_name,
            place=ctx.restaurant.get("location") or "",
            name=ctx.restaurant_name,
            caption=ws["caption"],
            hashtags=kit.get("hashtags", []) if kit else [],
            overlay=overlay,
            image=media.get("preview") if media and media["kind"] == "image" else None,
            video=bool(media and media["kind"] == "video"),
            content_format=actual_format,
            colors=ws["facts"].get("brand_colors") or [],
            cutoff=cutoff,
            position=preview_index + 1 if len(slots) > 1 else None,
            total=len(slots) if len(slots) > 1 else None,
        ),
        unsafe_allow_html=True,
    )


def _render_uploads(ctx: WorkspaceContext, ws: dict) -> None:
    resp = ws.get("resp")
    actual_format = kitlib.execution_format(resp, ctx.idea["content_format"])
    slots = _asset_slots(resp)

    if not resp:
        st.markdown(
            '<p class="hint">Create the posting guide first. Rawaj will then tell you how many images or videos the idea needs.</p>',
            unsafe_allow_html=True,
        )
        return

    st.markdown(
        f'<p class="hint">{len(slots)} asset{"s" if len(slots) != 1 else ""} for this {escape(kitlib.format_name(actual_format).lower())}. Uploading here is optional; it helps you preview/check the final content.</p>',
        unsafe_allow_html=True,
    )

    for index, (storage_key, label, accepted_kind) in enumerate(slots):
        st.markdown(f'<div class="dl"><small>{escape(label)}</small></div>', unsafe_allow_html=True)
        media = ws["assets"].get(storage_key)
        if media is None:
            types = ["png", "jpg", "jpeg", "webp"]
            if accepted_kind in {"video", "image_or_video"}:
                types += ["mp4", "mov"]
            upload = st.file_uploader(
                label,
                type=types,
                key=f"asset_up_{ctx.wid}_{storage_key}_{ws['upload_generation']}",
                label_visibility="collapsed",
            )
            if upload is not None:
                try:
                    ws["assets"][storage_key] = _read_upload(upload, actual_format)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    st.rerun()
            continue

        st.markdown(
            f'<p class="hint" style="margin:.1rem 0 .35rem;"><b>{escape(media["name"])}</b></p>',
            unsafe_allow_html=True,
        )
        if media["kind"] == "video":
            st.video(media["bytes"])
            st.markdown(
                '<p class="hint">Video is previewed but not visually evaluated.</p>',
                unsafe_allow_html=True,
            )
        else:
            levels = {"ok": ("good", "check"), "warn": ("limit", "alert"), "bad": ("bad", "alert")}
            rows = "".join(
                f'<div class="note {levels[level][0]}"><span class="dot">{icon(levels[level][1], 13, 2.4)}</span><span>{escape(text)}</span></div>'
                for level, text in media["check"]["items"]
            )
            st.markdown(f'<div class="notes one">{rows}</div>', unsafe_allow_html=True)

        if st.button(
            "Remove",
            key=f"asset_rm_{ctx.wid}_{storage_key}",
            type="tertiary",
            icon=":material/close:",
        ):
            del ws["assets"][storage_key]
            ws["upload_generation"] += 1
            st.rerun()


def _render_side(ctx: WorkspaceContext, ws: dict) -> None:
    with st.container(key="side_sticky"):
        with st.container(key="card_preview"):
            st.markdown(
                '<div class="card-head"><h3 class="card-title">Live preview</h3><span class="muted">Updates as you edit</span></div>',
                unsafe_allow_html=True,
            )
            _render_preview(ctx, ws)

        with st.container(key="card_upload"):
            st.markdown(
                '<div class="card-head"><h3 class="card-title">Your content assets</h3><span class="muted">Stays in this session</span></div>',
                unsafe_allow_html=True,
            )
            _render_uploads(ctx, ws)


# ---------------------------------------------------------------------------
# Final hand-off and completion
# ---------------------------------------------------------------------------


def _mark_posted(ctx: WorkspaceContext, ws: dict, stats: dict) -> None:
    ws["before"] = stats["done"]
    try:
        api.set_day_status(ctx.restaurant["id"], ctx.task["day"], "Completed")
    except api.ApiError as exc:
        st.session_state.plan_error = exc.detail or str(exc)


def _undo_posted(ctx: WorkspaceContext, ws: dict) -> None:
    ws["before"] = None
    try:
        api.set_day_status(ctx.restaurant["id"], ctx.task["day"], "Planned")
    except api.ApiError as exc:
        st.session_state.plan_error = exc.detail or str(exc)


def _save_extras(ctx: WorkspaceContext) -> None:
    link = (st.session_state.get(f"link_{ctx.wid}") or "").strip()
    if link and not link.lower().startswith(("http://", "https://")):
        st.session_state.plan_error = "Paste the full link, starting with https://"
        return

    how = st.session_state.get(f"how_{ctx.wid}")
    outcome = next((code for code, label in kitlib.OUTCOMES.items() if label == how), None)
    try:
        api.set_day_status(
            ctx.restaurant["id"],
            ctx.task["day"],
            "Completed",
            post_url=link,
            outcome=outcome,
        )
    except api.ApiError as exc:
        st.session_state.plan_error = exc.detail or str(exc)


def _render_take_to_instagram(ctx: WorkspaceContext, ws: dict, stats: dict) -> None:
    resp = ws["resp"]
    if _kit_is_stale(ws):
        st.warning("Update the posting guide first. The current guide was generated from older facts.")
        return

    kit = resp["kit"]
    st.markdown(
        """
        <div class="eyebrow" style="color:var(--blue);">Take it to Instagram</div>
        <h2 style="font:600 22px var(--head); margin:.4rem 0 .3rem;">Everything you need is ready.</h2>
        <p class="muted" style="margin:0 0 .8rem;">Copy the caption or the full execution guide, create the post in Instagram, then mark it as posted.</p>
        """,
        unsafe_allow_html=True,
    )

    keep(f"copy_{ctx.wid}", "Caption")
    what = st.segmented_control(
        "Copy",
        ["Caption", "Hashtags", "Execution guide", "Whole kit"],
        key=f"copy_{ctx.wid}",
        label_visibility="collapsed",
    ) or "Caption"
    copy_text = {
        "Caption": ws["caption"],
        "Hashtags": kitlib.hashtag_text(kit["hashtags"]),
        "Execution guide": kitlib.shot_list_text(kit["shoot"]),
        "Whole kit": kitlib.whole_kit_text(
            resp,
            ws["caption"],
            ws["overlay"],
            ctx.when,
            f"POST KIT · {ctx.restaurant_name} · {ctx.when} · {kitlib.format_name(kit['shoot']['format'])}",
        ),
    }[what]
    st.code(copy_text, language=None, wrap_lines=True)

    keep(f"sch_{ctx.wid}", ws["scheduled"])
    ws["scheduled"] = st.checkbox(
        "I've scheduled it in Instagram",
        key=f"sch_{ctx.wid}",
    )

    st.markdown(
        f'<div class="flag good">{icon("info", 15)}<span><b>You publish it yourself.</b> Rawaj prepares and checks the guide; it does not publish to Instagram yet.</span></div>',
        unsafe_allow_html=True,
    )
    one = st.columns([1, 1.4])
    
    if one.button(
        "Mark as posted",
        icon=":material/check_circle:",
        type="primary",
        key=f"post_{ctx.wid}",
    ):
        _mark_posted(ctx, ws, stats)
        st.rerun()


def _render_after_posting(ctx: WorkspaceContext, ws: dict, stats: dict) -> None:
    st.markdown(
        f"""
        <div class="done-head"><span class="badge">{icon('check', 20, 2.6)}</span>
          <div><b>Posted.</b><span>“{escape(ctx.idea['name'])}” is marked complete on your calendar.</span></div></div>
        """,
        unsafe_allow_html=True,
    )

    moved = ws["before"] is not None and ws["before"] != stats["done"]
    counted = (
        f"{ws['before']} → {stats['done']} of {stats['total']} actions"
        if moved else f"{stats['done']} of {stats['total']} actions completed"
    )
    st.markdown(
        f"""
        <div style="margin:1rem 0 .3rem;"><div class="card-head" style="margin-bottom:.4rem;"><h3 class="card-title">Strategy progress</h3>
        <span class="muted"><b>{counted}</b></span></div>
        <div class="bar-row"><div class="bar"><i style="width:{stats['percent']}%"></i></div><b>{stats['percent']}%</b></div></div>
        """,
        unsafe_allow_html=True,
    )

    following = kitlib.next_task(ctx.plan, ctx.task)
    if following:
        label = " · ".join(
            part for part in (
                f"{following['date']:%a %d %b}",
                following["format"] if following.get("typed") else "",
                following["title"],
            ) if part
        )
        st.markdown(
            f'<div class="readout" style="margin-top:.8rem;"><small>Next on your calendar</small><b>{escape(label)}</b></div>',
            unsafe_allow_html=True,
        )
        if st.button("Plan the next post", icon=":material/arrow_forward:", type="primary", key=f"next_{ctx.wid}"):
            st.session_state.selected_task = following["id"]
            st.rerun()

    st.markdown('<div class="dl" style="margin-top:1rem;"><small>Optional</small></div>', unsafe_allow_html=True)
    keep(f"link_{ctx.wid}", ctx.task.get("post_url", ""))
    keep(f"how_{ctx.wid}", kitlib.OUTCOMES.get(ctx.task.get("outcome", "")))
    st.text_input(
        "Link to your post",
        key=f"link_{ctx.wid}",
        placeholder="https://www.instagram.com/p/...",
        on_change=_save_extras,
        args=(ctx,),
    )
    how = st.pills(
        "How did it go?",
        list(kitlib.OUTCOMES.values()),
        selection_mode="single",
        key=f"how_{ctx.wid}",
        on_change=_save_extras,
        args=(ctx,),
    )
    code = next((c for c, label in kitlib.OUTCOMES.items() if label == how), None)
    if code:
        st.markdown(
            f'<div class="readout"><small>Your read</small>{escape(kitlib.outcome_readout(code, ctx.idea["name"], ctx.idea["content_format"]))}</div>',
            unsafe_allow_html=True,
        )

    if st.button("Undo", icon=":material/undo:", type="tertiary", key=f"undo_{ctx.wid}"):
        _undo_posted(ctx, ws)
        st.rerun()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def render(restaurant: dict, plan: dict, task: dict, idea: dict) -> None:
    """Render the complete idea → executable post workflow."""
    ctx = WorkspaceContext(
        restaurant=restaurant,
        plan=plan,
        task=task,
        idea=idea,
        wid=_workspace_id(restaurant, task, idea),
        restaurant_name=plan.get("restaurant_name") or restaurant["name"],
        when=f"{task['date']:%A %d %b}",
    )
    ws = _get_workspace(ctx)
    stats = progress(plan["tasks"])
    posted = task.get("status") == "Completed"

    _render_progress(ctx, ws, stats, posted)
    _render_why(ctx)

    left, right = st.columns([1.55, 1], gap="medium")
    with left:
        _render_facts(ctx, ws)
        if ws.get("resp"):
            _render_kit(ctx, ws)

    with right:
        _render_side(ctx, ws)

    if ws.get("resp") or posted:
        with left:
            with st.container(key="card_done" if posted else "card_end"):
                if st.session_state.get("plan_error"):
                    st.error(st.session_state.pop("plan_error"))
                if posted:
                    _render_after_posting(ctx, ws, stats)
                else:
                    _render_take_to_instagram(ctx, ws, stats)
