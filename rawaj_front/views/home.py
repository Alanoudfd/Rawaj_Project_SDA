from datetime import datetime
from html import escape

import streamlit as st

from ui import api
from ui.components import current_restaurant, footer, page_head, topbar
from ui.data import BUSINESS
from ui.icons import icon

TIERS = [
    ("total", "Total gaps", ""),
    ("high", "High", "high"),
    ("moderate", "Moderate", "moderate"),
    ("low", "Low", "low"),
    ("strengths", "Strengths", ""),
    ("data_limitations", "Data limitations", ""),
]
SEVERITY_CHIP = {"High": " sev-high", "Moderate": " sev-moderate", "Medium": " sev-moderate", "Low": " sev-low"}


def notes_card(key: str, title: str, subtitle: str, items: list[str], kind: str, symbol: str) -> None:
    """A titled card listing short sentences in two columns (used for strengths and data limitations)."""
    with st.container(key=key):
        rows = "".join(
            f'<div class="note {kind}"><span class="dot">{icon(symbol, 13, 2.4)}</span><span>{escape(text)}</span></div>'
            for text in items
        )
        st.markdown(
            f"""
            <div class="card-head"><h3 class="card-title">{title} · {len(items)}</h3></div>
            <p class="card-sub">{subtitle}</p>
            <div class="notes">{rows}</div>
            """,
            unsafe_allow_html=True,
        )


def _updated(stamp: str | None) -> str:
    try:
        return f"Updated {datetime.fromisoformat(stamp).astimezone():%d %b %H:%M}"
    except (TypeError, ValueError):
        return ""


@st.fragment(run_every=5)
def live_gaps() -> None:
    restaurant = current_restaurant()
    if restaurant is None:
        st.warning(f"No restaurants to show. Check that the Rawaj API is running at {api.API_URL}.")
        return
    try:
        data = api.get_gaps(restaurant["id"])
    except api.ApiError as exc:
        st.warning(f"Could not load the marketing gaps from the Rawaj API. {exc}")
        return

    counts, gaps = data["counts"], data["gaps"]
    st.markdown(
        '<div class="tiers">'
        + "".join(
            f'<div class="tier {extra}{" zero" if extra and not counts[key] else ""}">'
            f"<small>{label}</small><b>{counts[key]}</b></div>"
            for key, label, extra in TIERS
        )
        + "</div>",
        unsafe_allow_html=True,
    )

    main, side = st.columns([2.2, 1], gap="medium")

    with main:
        with st.container(key="card_gaps"):
            if gaps:
                rows = "".join(
                    f"""
                    <div class="gap">
                      <span class="num">{i:02d}</span>
                      <div class="body"><b>{escape(g['gap'])}</b><span>{escape(g['recommendation_focus'])}</span></div>
                      <span class="chip{SEVERITY_CHIP.get(g['severity'], '')}">{escape(g['severity'] or 'Unrated')}</span>
                    </div>"""
                    for i, g in enumerate(gaps, 1)
                )
                st.markdown(
                    f"""
                    <div class="card-head"><h3 class="card-title">Where {escape(data['restaurant_name'])} can grow</h3>
                    <span class="muted">{counts['total']} gaps · {_updated(data['created_at'])}</span></div>{rows}
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="empty">
                      <div class="ring">{icon('target', 26)}</div>
                      <h3>No marketing gaps yet.</h3>
                      <p>Run research to generate the latest qualification analysis.</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    with side:
        with st.container(key="card_next"):
            st.markdown(
                f"""
                <div class="eyebrow" style="letter-spacing:0; text-transform:none; font-size:11px; color:var(--navy);">
                  {icon('sparkles', 15)} <b>Your next direction</b>
                </div>
                <p class="muted" style="margin:.7rem 0 0;">Your audience is shaped around {escape(BUSINESS['audience'])}.</p>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Refresh", type="primary", key="refresh_gaps"):
                st.rerun(scope="fragment")
            st.markdown(
                '<div class="status"><b>live</b><span>This page reads the latest results from the Rawaj API.</span></div>',
                unsafe_allow_html=True,
            )

    if data["strengths"]:
        notes_card(
            "card_strengths", "Strengths", "What already works well.",
            data["strengths"], "good", "check",
        )
    if data["data_limitations"]:
        notes_card(
            "card_limits", "Data limitations", "What the analysis could not measure, so read these results with care.",
            data["data_limitations"], "limit", "info",
        )


topbar("Home")
page_head("Marketing gaps", badge="Marketing assessment")
live_gaps()
footer()
