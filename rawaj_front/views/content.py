from html import escape

import streamlit as st

from ui.components import current_restaurant, footer, topbar
from ui.icons import icon
from ui.ideas import chosen_idea_card, fetch_ideas, has_ideas, idea_cards
from ui.plan import load_or_stop, period_label

restaurant = current_restaurant()
plan = load_or_stop(restaurant)
PERIOD = period_label(plan)
context = restaurant.get("context") or {}
NOT_SET = "Not provided yet"


def saved(*names: str) -> str:
    """The first of these saved context fields that has a value (a list is joined), else a plain 'not provided'."""
    for name in names:
        value = context.get(name)
        text = ", ".join(str(v) for v in value if v) if isinstance(value, (list, tuple)) else str(value or "").strip()
        if text:
            return text
    return NOT_SET


BUSINESS = {  # everything here is read from the restaurant saved in the database
    "name": plan["restaurant_name"] or restaurant["name"],
    "city": restaurant.get("location") or NOT_SET,
    "type": saved("business_type").title() if saved("business_type") != NOT_SET else "",
    "around": saved("signature_items", "cuisine"),
    "voice": saved("tone", "brand_tone"),
    "language": saved("language"),
}
WHERE = " · ".join(part for part in (BUSINESS["type"], BUSINESS["city"]) if part)
tasks = {t["id"]: t for t in plan["tasks"]}
task_ids = list(tasks)
if st.session_state.get("selected_task") not in tasks:
    st.session_state.selected_task = task_ids[0]

topbar("Content Creation")

# Context row + planning month
ctx, month = st.columns([3, 1.3], vertical_alignment="center")
ctx.markdown(
    f'<div class="ctx-row">{icon("utensils", 15)}<b>{escape(BUSINESS["name"])}</b>'
    f'{"&nbsp;·&nbsp;" + escape(BUSINESS["type"]) if BUSINESS["type"] else ""}</div>',
    unsafe_allow_html=True,
)
with month:
    label, picker = st.columns([1, 1.4], vertical_alignment="center", gap="small")
    label.markdown(
        f'<div class="ctx-row" style="justify-content:flex-end;">{icon("calendar", 15)} Planning period</div>',
        unsafe_allow_html=True,
    )
    picker.selectbox("Planning period", [PERIOD], label_visibility="collapsed")

# Hero
st.markdown(
    f"""
    <div class="hero-card">
      <div>
        <div class="eyebrow"><span class="dot"></span>Content creation &nbsp;·&nbsp; {PERIOD}</div>
        <h1>Bring your brand <em>to life.</em></h1>
        <p>Content that sounds like you, looks like your business, and gives people a reason to stop scrolling.</p>
      </div>
      <div class="brand-chip">{icon('utensils', 22)}
        <div><b>{escape(BUSINESS['name'])}</b><span>{escape(WHERE)}</span></div>
      </div>
    </div>
    <div class="strip" style="margin-top:1rem;">
      <div><small>CREATED AROUND</small><span>{escape(BUSINESS['around'])}</span></div>
      <div><small>YOUR VOICE</small><span>{escape(BUSINESS['voice'])}</span></div>
      <div><small>CONTENT LANGUAGE</small><span>{escape(BUSINESS['language'])}</span></div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Task picker
title_col, pick_col = st.columns([2, 1.3], vertical_alignment="bottom")
title_col.markdown(
    '<h2 class="section-title">What are we creating?</h2>'
    '<p class="muted" style="margin:.35rem 0 0;">Choose a task from your monthly plan.</p>',
    unsafe_allow_html=True,
)
picked = pick_col.selectbox(
    "Calendar task",
    task_ids,
    index=task_ids.index(st.session_state.selected_task),
    format_func=lambda i: f"{tasks[i]['date']:%b} {tasks[i]['date'].day} · {tasks[i]['format']} · {tasks[i]['title']}",
)
st.session_state.selected_task = picked
task = tasks[picked]
day = task["date"]
done = task["status"] == "Completed"

with st.container(key="card_task"):
    st.markdown(
        f"""
        <div class="task" style="border:0; padding:0;">
          <div class="ico">{icon('calendar', 20)}</div>
          <div>
            <div class="meta"><span class="chip">{escape(task['format'])}</span>
              <span>{day:%a, %b} {day.day}</span><span>{'Completed' if done else 'Planned'}</span></div>
            <h4>{escape(task['title'])}</h4>
            <p>{escape(task['text'])}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

if not task.get("ideas", True):  # a break or a profile update: there is nothing to create
    st.info(task.get("ideas_note", ""))
    footer()
    st.stop()

chosen_idea_card(restaurant, task)

# Studio
with st.container(key="card_studio"):
    st.markdown(
        f"""
        <div class="eyebrow" style="color:var(--blue);">{icon('sparkles', 14)} Content studio</div>
        <h2>Find your next creative direction.</h2>
        <p class="muted" style="margin:0;">Ideas are shaped by <b>{escape(BUSINESS['name'])}</b>'s profile, monthly strategy, and this calendar task.</p>
        """,
        unsafe_allow_html=True,
    )
    with st.container(key="panel_guide"):
        guidance = st.text_area(
            "Guide the ideas (optional)",
            key=f"guidance_{picked}",
            placeholder="For example: keep it playful, feature our signature item, and make it easy to film on a phone.",
            height=80,
        )
        note, action = st.columns([3, 1], vertical_alignment="center")
        note.markdown(
            '<span class="muted" style="font-size:10.5px;">Turn an idea into your own photos, video, and voice.</span>',
            unsafe_allow_html=True,
        )
        with action:
            cached = has_ideas(restaurant, task)
            if st.button(
                "None fit? Generate others" if cached else "Generate content ideas",
                icon=":material/auto_awesome:", type="primary", key="generate",
            ):
                fetch_ideas(restaurant, task, cached, guidance)
                st.rerun()

    if st.session_state.get("idea_error"):
        st.error(st.session_state.pop("idea_error"))
    if has_ideas(restaurant, task):
        idea_cards(restaurant, task, "content")
    else:
        st.markdown(
            f"""
            <div class="placeholder">
              <div class="ico">{icon('sparkles', 20)}</div>
              <div><b>A good post starts with a clear idea.</b>
              <span>Generate a few directions, choose your favorite, and save it to this task.
              Your saved idea stays with your calendar.</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

footer()
