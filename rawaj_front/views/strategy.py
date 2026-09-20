import calendar
from datetime import date
from html import escape

import streamlit as st

from ui.components import current_restaurant, footer, page_head, topbar
from ui.icons import icon
from ui.plan import by_date, load_or_stop, period_label, progress, toggle

SEVERITY_CHIP = {"High": "sev-high", "Moderate": "sev-moderate", "Medium": "sev-moderate", "Low": "sev-low"}

restaurant = current_restaurant()
plan = load_or_stop(restaurant)
tasks = by_date(plan["tasks"])
stats = progress(plan["tasks"])
name = plan["restaurant_name"] or restaurant["name"]

if st.session_state.get("selected_date") not in tasks:
    today = date.today()
    st.session_state.selected_date = today if today in tasks else min(tasks)


def select_day(day) -> None:
    st.session_state.selected_date = day


def open_ideas(task_id) -> None:
    st.session_state.selected_task = task_id


def short(text: str, limit: int = 14) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


topbar("Monthly Strategy")
page_head(
    "Monthly strategy",
    f"{period_label(plan)} · built by the Strategy Agent from your marketing assessment.",
    badge="Started after you said Interested" if plan.get("interest_event_id") else "30-day plan",
    badge_icon=icon("utensils", 13),
)

main, side = st.columns([2.1, 1], gap="medium")

with main:
    with st.container(key="card_north"):
        targets = "".join(
            f"""
            <div class="pillar">
              <span class="n">{i:02d}</span>
              <div class="t"><b>{escape(text)}</b></div>
            </div>"""
            for i, text in enumerate(plan["targets"], 1)
        )
        st.markdown(
            f"""
            <div class="north">
              <div class="badge">{icon('target', 20)}</div>
              <div>
                <div class="eyebrow">Your 30-day targets</div>
                <h3>What {escape(name)} is working toward</h3>
              </div>
            </div>
            {targets or '<p class="muted">No targets were set for this plan.</p>'}
            """,
            unsafe_allow_html=True,
        )

    with st.container(key="card_pillars"):
        gaps = "".join(
            f"""
            <div class="pillar">
              <span class="n">{i:02d}</span>
              <div class="t"><b>{escape(g['gap'])}</b><span>{escape(g['key_point'])}</span></div>
              <span class="chip {SEVERITY_CHIP.get(g['severity'], '')}">{escape(g['severity'] or 'Unrated')}</span>
              {f'<span class="signal">{escape(g["highlight"])} {escape(g["highlight_label"] or "")}</span>' if g['highlight'] else ''}
            </div>"""
            for i, g in enumerate(plan["gaps"], 1)
        )
        st.markdown(
            f"""
            <div class="card-head"><h3 class="card-title">Where the plan starts</h3>
            <span class="muted" style="font-size:10.5px;">{len(plan['gaps'])} priority gaps</span></div>
            {gaps or '<p class="muted">No priority gaps were recorded.</p>'}
            """,
            unsafe_allow_html=True,
        )

with side:
    points = "".join(
        f'<div class="pt">{icon("check", 13)}<span><b>{escape(s["service"])}</b>'
        f'{"<br>" + escape(s["why_this_service_fits"]) if s["why_this_service_fits"] else ""}</span></div>'
        for s in plan["services"]
    )
    st.markdown(
        f"""
        <div class="focus">
          <div class="top">{icon('lightbulb', 15)} Recommended for you</div>
          <h3>How we can help {escape(name)} grow.</h3>
          <p>Services matched to the gaps found in your assessment.</p>
          {points or '<p>No services were recommended.</p>'}
        </div>
        """,
        unsafe_allow_html=True,
    )

if plan["trends"]:
    with st.container(key="card_trends"):
        rows = "".join(
            f'<div class="note good"><span class="dot">{icon("sparkles", 13, 2.2)}</span>'
            f'<span>{escape(t["insight"])}'
            + (f' <a href="{escape(t["source_url"], quote=True)}" target="_blank" rel="noopener noreferrer">Source</a>' if t["source_url"] else "")
            + "</span></div>"
            for t in plan["trends"]
        )
        st.markdown(
            f"""
            <div class="card-head"><h3 class="card-title">Market trends behind the plan · {len(plan['trends'])}</h3></div>
            <div class="notes">{rows}</div>
            """,
            unsafe_allow_html=True,
        )


def progress_card() -> None:
    """How many days are planned and how many are completed."""
    weeks = "".join(
        f'<span class="chip{" sev-low" if done == total else ""}">Week {number} · {done}/{total}</span>'
        for number, (done, total) in stats["weeks"].items()
    )
    st.markdown(
        f"""
        <div class="card-head"><h3 class="card-title">Strategy progress · {period_label(plan)}</h3>
        <span class="muted">{stats['done']} of {stats['total']} completed</span></div>
        <div class="tiers three">
          <div class="tier"><small>Days in the plan</small><b>{stats['total']}</b></div>
          <div class="tier low{' zero' if not stats['done'] else ''}"><small>Completed</small><b>{stats['done']}</b></div>
          <div class="tier{' zero' if not stats['remaining'] else ''}"><small>Remaining</small><b>{stats['remaining']}</b></div>
        </div>
        <div class="bar-row"><div class="bar"><i style="width:{stats['percent']}%"></i></div><b>{stats['percent']}%</b></div>
        <div class="formats">{weeks}</div>
        """,
        unsafe_allow_html=True,
    )


with st.container(key="card_progress"):
    progress_card()

page_head("Content calendar", "Choose a day to see what to publish and when, and track your progress.")

cal_col, detail_col = st.columns([1.75, 1], gap="medium")

with cal_col:
    with st.container(key="card_calendar"):
        st.markdown(
            '<div class="dow">' + "".join(f"<span>{d}</span>" for d in ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")) + "</div>",
            unsafe_allow_html=True,
        )
        # The 30 days usually straddle two calendar months: draw each month that the plan touches.
        for year, month in sorted({(d.year, d.month) for d in tasks}):
            st.markdown(f'<h3 class="cal-title">{date(year, month, 1):%B %Y}</h3>', unsafe_allow_html=True)
            for week in calendar.Calendar(firstweekday=0).monthdatescalendar(year, month):
                cols = st.columns(7, gap="xsmall")
                for col, day in zip(cols, week):
                    if day.month != month:
                        col.markdown('<div class="blank"></div>', unsafe_allow_html=True)
                        continue
                    day_tasks = tasks.get(day, [])
                    finished = bool(day_tasks) and all(t["status"] == "Completed" for t in day_tasks)
                    tag = short(day_tasks[0]["title"]) if len(day_tasks) == 1 else f"{len(day_tasks)} tasks"
                    label = f"{day.day}{' ✓' if finished else ''}\n\n{tag}" if day_tasks else str(day.day)
                    picked = day == st.session_state.selected_date
                    col.button(
                        label,
                        key=f"{'dayon' if picked else 'day'}_{day.isoformat()}",
                        on_click=select_day,
                        args=(day,),
                        use_container_width=True,
                    )

with detail_col:
    with st.container(key="card_selected"):
        day = st.session_state.selected_date
        st.markdown(
            f'<div class="selected-head"><span class="eyebrow">Selected date</span><b>{day:%a, %b} {day.day}</b></div>',
            unsafe_allow_html=True,
        )
        if st.session_state.get("plan_error"):
            st.error(st.session_state.pop("plan_error"))
        day_tasks = tasks.get(day, [])
        for task in day_tasks:
            finished = task["status"] == "Completed"
            st.markdown(
                f"""
                <div class="task">
                  <div class="ico">{icon('check' if finished else 'calendar', 18)}</div>
                  <div>
                    <div class="meta"><span class="fmt">{escape(task['format'])}</span>
                      <span>{'Completed' if finished else 'Planned'}</span></div>
                    <h4>{escape(task['title'])}</h4>
                    <p>{escape(task['text'])}</p>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            a, b = st.columns([1.2, 1])
            if a.button(
                "Get content ideas", icon=":material/auto_awesome:", type="primary", key=f"ideas_{task['id']}",
                on_click=open_ideas, args=(task["id"],),
            ):
                st.switch_page("views/content.py")
            b.button(
                "Mark incomplete" if finished else "Mark complete", icon=":material/check:",
                type="tertiary", key=f"mark_{task['id']}", on_click=toggle,
                args=(restaurant["id"], task),
            )
        if not day_tasks:
            st.markdown(
                f'<p class="muted">Nothing is planned for this day at {escape(name)}.</p>',
                unsafe_allow_html=True,
            )

footer()
