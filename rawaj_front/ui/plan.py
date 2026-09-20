"""The Strategy Agent's 30-day strategy, shared by the Strategy and Content pages (data comes from the API)."""

from datetime import date
from html import escape

import streamlit as st

from ui import api
from ui.icons import icon


def load(restaurant: dict) -> dict | None:
    """The restaurant's latest agent strategy with its days as tasks; None if none exists yet."""
    plan = api.get_agent_strategy(restaurant["id"])
    if plan is None:
        return None
    plan["start"] = date.fromisoformat(plan["start_date"])
    plan["end"] = date.fromisoformat(plan["end_date"])
    plan["tasks"] = [
        {
            "id": f"day-{d['day']}", "day": d["day"], "date": date.fromisoformat(d["date"]),
            "format": f"Day {d['day']}", "title": d["focus"] or f"Day {d['day']}",
            "text": d["action"], "status": d["status"],
        }
        for d in plan["days"]
    ]
    return plan


def period_label(plan: dict) -> str:
    start, end = plan["start"], plan["end"]
    return f"{start:%d %b} – {end:%d %b %Y}"


def load_or_stop(restaurant: dict | None) -> dict:
    """Load the plan, or explain why it is unavailable and stop the page."""
    if restaurant is None:
        st.warning(f"No restaurant found. Check that the Rawaj API is running at {api.API_URL}.")
        st.stop()
    try:
        plan = load(restaurant)
    except api.ApiError as exc:
        st.warning(f"Could not load the strategy from the Rawaj API. {exc}")
        st.stop()
    if plan is None or not plan["tasks"]:
        st.markdown(
            f"""
            <div class="empty">
              <div class="ring">{icon('calendar', 26)}</div>
              <h3>No strategy yet for {escape(restaurant['name'])}.</h3>
              <p>The Strategy Agent builds the 30-day plan once the restaurant confirms interest.
              It will appear here as soon as it is saved.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()
    return plan


def by_date(tasks: list[dict]) -> dict[date, list[dict]]:
    days: dict[date, list[dict]] = {}
    for task in tasks:
        days.setdefault(task["date"], []).append(task)
    return days


def progress(tasks: list[dict]) -> dict:
    """Counts for the plan: total, completed, remaining, percent and completion per week."""
    done = sum(t["status"] == "Completed" for t in tasks)
    weeks: dict[int, list[int]] = {}
    for task in tasks:
        counts = weeks.setdefault((task["day"] - 1) // 7 + 1, [0, 0])
        counts[1] += 1
        counts[0] += task["status"] == "Completed"
    total = len(tasks)
    return {
        "total": total, "done": done, "remaining": total - done,
        "percent": round(100 * done / total) if total else 0, "weeks": dict(sorted(weeks.items())),
    }


def toggle(restaurant_id: int, task: dict) -> None:
    """Button callback: flip a day between Planned and Completed through the API."""
    status = "Planned" if task["status"] == "Completed" else "Completed"
    try:
        api.set_day_status(restaurant_id, task["day"], status)
    except api.ApiError as exc:
        st.session_state.plan_error = str(exc)
