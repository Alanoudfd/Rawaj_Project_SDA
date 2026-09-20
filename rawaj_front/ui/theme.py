"""Rawaj design system. Palette is limited to navy, light blue, white and black."""

import re
from urllib.parse import quote

import streamlit as st

from ui.icons import _PATHS


def _input_icon(name: str) -> str:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" '
        'fill="none" stroke="#0E1E3A" stroke-opacity=".55" stroke-width="1.8" '
        f'stroke-linecap="round" stroke-linejoin="round">{_PATHS[name]}</svg>'
    )
    return f'url("data:image/svg+xml,{quote(svg)}")'


FONTS = (
    "@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700"
    "&family=Inter:wght@400;500;600&display=swap');"
)

CSS = """
:root {
  --navy: #0E1E3A;
  --navy-2: #182C4E;
  --navy-deep: #0A1730;
  --blue: #5BA4E6;
  --blue-soft: #EAF3FC;
  --blue-tint: #F5F9FE;
  --blue-line: #D3E4F6;
  --white: #FFFFFF;
  --black: #0A0A0A;
  --muted: rgba(14, 30, 58, .62);
  --head: 'Space Grotesk', system-ui, sans-serif;
  --body: 'Inter', system-ui, sans-serif;
}

/* ---------- base ---------- */
html, body, .stApp, [data-testid="stAppViewContainer"] {
  background: var(--blue-tint) !important;
  color: var(--black);
  font-family: var(--body);
  font-size: 14px;
}
.stApp p, .stApp label, .stApp li, .stApp input, .stApp textarea, .stApp button,
.stApp [data-testid="stMarkdownContainer"] { font-family: var(--body); }
.stApp h1, .stApp h2, .stApp h3, .head { font-family: var(--head) !important; color: var(--black); }
header[data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stDecoration"],
[data-testid="stStatusWidget"], footer, #MainMenu { display: none !important; }
[data-testid="stMainBlockContainer"] { max-width: 1240px; padding: 1.25rem 2rem 2rem; }
[data-testid="stVerticalBlock"] { gap: 1rem; }
[data-testid="stElementContainer"]:has(> [data-testid="stMarkdown"] style) { display: none; }
.ic { flex: none; vertical-align: middle; }
[data-testid="stMarkdownContainer"] :is(p, h1, h2, h3, h4) { margin: 0; padding: 0; }
[data-testid="stMarkdown"], [data-testid="stMarkdownContainer"] { margin-bottom: 0 !important; }

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
  background: var(--white) !important;
  border-right: 1px solid var(--blue-line);
  min-width: 250px !important; width: 250px !important;
}
[data-testid="stSidebarHeader"] { display: none; }
[data-testid="stSidebarUserContent"] { padding: 1.4rem 1rem 1rem; }
[data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
  min-height: calc(100vh - 2.4rem); gap: .35rem;
}
[data-testid="stLayoutWrapper"]:has(> .st-key-side_bottom) { margin-top: auto; }
.brand { display: flex; align-items: center; gap: .7rem; margin-bottom: .9rem; }
.brand-mark {
  width: 34px; height: 34px; border-radius: 10px; background: var(--navy); color: var(--white);
  display: grid; place-items: center;
}
.brand-name { font: 600 19px/1.1 var(--head); color: var(--black); margin: 0; }
.brand-tag { font-size: 10.5px; color: var(--muted); margin: 3px 0 0; }
.workspace {
  display: flex; align-items: center; gap: .7rem; padding: .6rem .75rem;
  border: 1px solid var(--blue-line); border-radius: 12px; margin-bottom: .8rem;
}
.workspace .pill {
  width: 24px; height: 24px; border-radius: 50%; background: var(--blue-soft); color: var(--navy);
  display: grid; place-items: center; font: 600 11px var(--head);
}
.workspace small { display: block; font-size: 10px; color: var(--muted); }
.workspace strong { font: 500 14px var(--head); }
[data-testid="stPageLink-NavLink"] {
  border-radius: 10px; padding: .5rem .7rem; gap: .65rem; color: var(--navy);
}
[data-testid="stPageLink-NavLink"] p { font: 500 13px var(--body); color: inherit; }
[data-testid="stPageLink-NavLink"]:hover { background: var(--blue-soft); }
[data-testid="stPageLink-NavLink"][aria-current="page"] { background: var(--blue-soft); color: var(--black); }
[data-testid="stPageLink-NavLink"][aria-current="page"] p { font-weight: 600; }
.rooted {
  border: 1px solid var(--blue-line); background: var(--blue-tint); border-radius: 14px; padding: .9rem;
}
.rooted .row { display: flex; justify-content: space-between; align-items: flex-start; }
.rooted b { font: 600 11.5px var(--head); color: var(--black); }
.rooted p { font-size: 10.5px; line-height: 1.55; color: var(--muted); margin: .45rem 0 .7rem; }
.rooted .tag { display: flex; align-items: center; gap: .45rem; font-size: 10.5px; color: var(--navy); }
.copyright { font-size: 10px; color: var(--muted); padding: .2rem .2rem 0; }

/* ---------- top bar ---------- */
.st-key-topbar {
  background: var(--white); border: 1.5px solid var(--navy); border-radius: 18px; padding: .55rem 1rem;
}
.st-key-topbar [data-testid="stVerticalBlock"] { gap: 0; }
.crumb { font-size: 11.5px; color: var(--muted); }
.crumb i { font-style: normal; padding: 0 .55rem; }
.crumb b { color: var(--navy); font-weight: 500; }
.user { display: flex; align-items: center; justify-content: flex-end; gap: .55rem; font: 600 11px var(--head); }
.avatar {
  width: 26px; height: 26px; border-radius: 50%; background: var(--blue-soft); color: var(--navy);
  display: grid; place-items: center; font: 600 11px var(--head);
}
.st-key-logout button {
  width: 34px; height: 34px; min-height: 0; padding: 0; border-radius: 10px;
  border: 1px solid var(--blue-line); background: var(--white); color: var(--navy);
}

/* ---------- headers, cards ---------- */
.page-head {
  display: flex; align-items: center; justify-content: space-between; gap: 1rem;
  background: linear-gradient(180deg, var(--blue-soft), var(--white));
  border: 1.5px solid var(--navy); border-radius: 22px; padding: 1.15rem 1.4rem;
}
.page-head h2 { font-size: 26px; font-weight: 600; margin: 0; letter-spacing: -.01em; }
.page-head p { margin: .35rem 0 0; font-size: 12px; color: var(--muted); }
.chip {
  display: inline-flex; align-items: center; gap: .4rem; padding: .3rem .8rem; border-radius: 999px;
  background: var(--blue-soft); border: 1px solid var(--blue-line); color: var(--navy);
  font: 500 10.5px var(--head); white-space: nowrap;
}
.chip.solid { background: var(--navy); border-color: var(--navy); color: var(--white); }
.chip.ghost { background: var(--white); }

[class*="st-key-card"] {
  background: var(--white); border: 1px solid var(--blue-line); border-radius: 20px; padding: 1.3rem 1.4rem;
}
.eyebrow {
  display: flex; align-items: center; gap: .5rem; font: 600 9.5px var(--head);
  letter-spacing: .12em; text-transform: uppercase; color: var(--muted);
}
.eyebrow .dot { width: 6px; height: 6px; border-radius: 50%; background: var(--blue); }
.card-title { font: 600 15px var(--head); margin: 0; color: var(--black); }
.muted { color: var(--muted); font-size: 12px; }

/* empty state */
.empty { text-align: center; padding: 3.5rem 1rem; }
.empty .ring { color: var(--navy); opacity: .7; }
.empty h3 { font: 600 19px var(--head); margin: 1rem 0 .5rem; }
.empty p { font-size: 12px; color: var(--muted); margin: 0 auto; max-width: 30rem; }
.st-key-card_gaps { min-height: 440px; }
.st-key-card_gaps .empty { padding-top: 7rem; }

.status {
  border-radius: 12px; padding: .7rem .9rem; margin-top: .3rem;
  background: var(--blue-soft); border: 1px solid var(--blue-line); color: var(--navy);
}
.status b { display: block; font: 600 10.5px var(--head); margin-bottom: 2px; }
.status span { font-size: 10.5px; }

.gap { display: flex; gap: 1rem; align-items: flex-start; padding: 1rem 0; border-top: 1px solid var(--blue-line); }
.gap:first-of-type { border-top: 0; padding-top: .4rem; }
.gap .num { font: 500 11px var(--head); color: var(--muted); width: 1.6rem; padding-top: 3px; }
.gap .body { flex: 1; }
.gap .body b { font: 600 14px var(--head); display: block; }
.gap .body span { font-size: 12px; color: var(--muted); line-height: 1.6; }

/* severity colors: red = High, yellow = Moderate, green = Low */
:root {
  --high: #D64545; --high-bg: #FDECEC; --high-line: #F4B8B8;
  --mod: #B98100;  --mod-bg: #FFF6D9;  --mod-line: #F0D27A;
  --low: #2E9E5B;  --low-bg: #E7F6EC;  --low-line: #A9DBBB;
}
.chip.sev-high { background: var(--high-bg); border-color: var(--high-line); color: var(--high); font-weight: 600; }
.chip.sev-moderate { background: var(--mod-bg); border-color: var(--mod-line); color: var(--mod); font-weight: 600; }
.chip.sev-low { background: var(--low-bg); border-color: var(--low-line); color: var(--low); font-weight: 600; }

.tiers { display: grid; grid-template-columns: repeat(6, 1fr); gap: .8rem; margin: 1rem 0; }
.tier {
  background: var(--white); border: 1px solid var(--blue-line); border-radius: 16px; padding: .9rem 1.1rem;
  --c: var(--navy);
}
.tier small { display: block; font: 600 9.5px var(--head); letter-spacing: .1em; text-transform: uppercase; color: var(--muted); }
.tier b { display: block; font: 600 28px var(--head); color: var(--c); margin-top: .2rem; }
.tier.high { --c: var(--high); background: var(--high-bg); border-color: var(--high-line); }
.tier.moderate { --c: var(--mod); background: var(--mod-bg); border-color: var(--mod-line); }
.tier.low { --c: var(--low); background: var(--low-bg); border-color: var(--low-line); }
.tier.high small, .tier.moderate small, .tier.low small { color: var(--c); }
.tier.zero { background: var(--white); border-style: dashed; }
.tier.zero b { color: var(--muted); }
@media (max-width: 1100px) { .tiers { grid-template-columns: repeat(3, 1fr); } }

/* strengths & data limitations */
.notes { display: grid; grid-template-columns: 1fr 1fr; gap: 0 2rem; margin-top: .6rem; }
.note { display: flex; gap: .7rem; align-items: flex-start; padding: .7rem 0; border-top: 1px solid var(--blue-line); font-size: 12.5px; line-height: 1.6; }
.note .dot {
  flex: none; width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; margin-top: 1px;
}
.note.good .dot { background: var(--low-bg); color: var(--low); }
.note.limit .dot { background: var(--mod-bg); color: var(--mod); }
.card-sub { font-size: 12px; color: var(--muted); margin: .2rem 0 0; }
@media (max-width: 900px) { .notes { grid-template-columns: 1fr; } }

/* strategy progress */
.tiers.three { grid-template-columns: repeat(3, 1fr); margin-bottom: .8rem; }
.bar-row { display: flex; align-items: center; gap: .9rem; }
.bar-row b { font: 600 13px var(--head); min-width: 2.6rem; text-align: right; }
.bar { flex: 1; height: 10px; border-radius: 999px; background: var(--blue-soft); overflow: hidden; }
.bar i { display: block; height: 100%; border-radius: inherit; background: var(--low); transition: width .4s; }
.formats { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: .9rem; }

/* strategy */
.north { display: flex; gap: 1rem; align-items: flex-start; }
.north .badge {
  width: 40px; height: 40px; border-radius: 12px; background: var(--blue-soft); color: var(--navy);
  display: grid; place-items: center; flex: none;
}
.north h3 { font: 600 19px/1.25 var(--head); margin: .5rem 0 .6rem; }
.north p { font-size: 12px; line-height: 1.7; color: var(--muted); margin: 0; }
.pillar { display: flex; align-items: flex-start; gap: 1.2rem; padding: 1rem 0; border-top: 1px solid var(--blue-line); }
.pillar .n { font: 500 10px var(--head); color: var(--muted); width: 1.4rem; padding-top: 3px; }
.pillar .t { flex: 1; }
.pillar .t b { font: 600 12.5px var(--head); display: block; margin-bottom: 3px; }
.pillar .t span { font-size: 11.5px; color: var(--muted); line-height: 1.6; }
.pillar .signal {
  font-size: 9.5px; color: var(--navy); background: var(--blue-soft); border: 1px solid var(--blue-line);
  border-radius: 12px; padding: .3rem .8rem; max-width: 9.5rem; text-align: center; line-height: 1.35;
}
.card-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: .6rem; }
.focus {
  background: var(--navy); color: var(--white); border-radius: 20px; padding: 1.3rem 1.4rem; min-height: 418px;
}
.focus .top { display: flex; align-items: center; gap: .6rem; font: 500 11px var(--head); }
.focus h3 { font: 600 24px/1.2 var(--head) !important; color: var(--white) !important; margin: 1.1rem 0 .9rem; letter-spacing: -.01em; }
.focus p { font-size: 11.5px; line-height: 1.6; color: rgba(255,255,255,.86); margin: 0 0 1.4rem; }
.focus .pt {
  display: flex; align-items: center; gap: .6rem; border-top: 1px solid rgba(255,255,255,.16);
  padding: .8rem 0; font-size: 10.5px;
}

/* calendar */
.dow { display: grid; grid-template-columns: repeat(7, 1fr); gap: .5rem; margin: .8rem 0 .2rem; }
.dow span { font: 500 8.5px var(--head); letter-spacing: .1em; color: var(--muted); text-align: center; }
.cal-title { font: 600 14px var(--head); margin: 0; }
[class*="st-key-day"] button {
  height: 60px; min-height: 60px; width: 100%; border-radius: 12px; padding: .4rem .55rem;
  background: var(--blue-tint); border: 1px solid var(--blue-line); box-shadow: none;
  display: flex; justify-content: flex-start; align-items: flex-start; color: var(--black);
}
[class*="st-key-day"] button:hover { background: var(--blue-soft); border-color: var(--navy); }
[class*="st-key-day"] button > div { display: block; width: 100%; }
[class*="st-key-day"] button [data-testid="stMarkdownContainer"] {
  width: 100%; text-align: left; display: flex; flex-direction: column; align-items: flex-start;
}
[class*="st-key-day"] button p { font: 500 11px/1.5 var(--head); margin: 0; }
[class*="st-key-day"] button p:nth-of-type(2) {
  font: 500 8.5px/1.4 var(--head); background: var(--blue-soft); color: var(--navy);
  border-radius: 6px; padding: 0 .4rem; width: fit-content; margin-top: 3px;
}
[class*="st-key-dayon"] button { border: 1.5px solid var(--navy); background: var(--blue-soft); }
[class*="st-key-dayon"] button p:nth-of-type(2) { background: var(--white); }
.blank { height: 60px; }
.selected-head { display: flex; justify-content: space-between; margin-bottom: .8rem; }
.selected-head b { font: 600 9.5px var(--head); color: var(--navy); }
.task {
  border: 1px solid var(--blue-line); border-radius: 14px; padding: 1rem 1.1rem;
  display: flex; gap: .9rem; align-items: flex-start;
}
.task .ico {
  width: 40px; height: 40px; border-radius: 12px; background: var(--blue-soft); color: var(--navy);
  display: grid; place-items: center; flex: none;
}
.task .meta { display: flex; gap: .6rem; align-items: center; font-size: 10.5px; color: var(--muted); }
.task .meta .fmt { font: 600 9.5px var(--head); letter-spacing: .1em; text-transform: uppercase; }
.task h4 { font: 600 16px var(--head); margin: .45rem 0 .3rem; }
.task p { font-size: 12px; color: var(--muted); margin: 0; line-height: 1.6; }
.st-key-card_selected [data-testid="stHorizontalBlock"] { gap: .6rem; }

/* content creation */
.ctx-row { display: flex; align-items: center; gap: .5rem; font-size: 11px; color: var(--muted); }
.ctx-row b { color: var(--navy); font-weight: 600; }
.hero-card {
  display: flex; justify-content: space-between; align-items: center; gap: 1.5rem; flex-wrap: wrap;
  background: linear-gradient(180deg, var(--blue-soft), var(--white)); border: 1.5px solid var(--navy);
  border-radius: 22px; padding: 1.4rem 1.6rem 1.5rem;
}
.hero-card h1 { font: 600 clamp(2.2rem, 4vw, 3.3rem)/1.05 var(--head) !important; letter-spacing: -.03em; margin: .9rem 0 1.1rem; }
.hero-card h1 em { font-style: normal; color: var(--blue); }
.hero-card p { margin: 0; font-size: 12.5px; color: var(--muted); }
.brand-chip {
  display: flex; align-items: center; gap: .8rem; background: var(--white); border: 1px solid var(--blue-line);
  border-radius: 14px; padding: .8rem 1.1rem;
}
.brand-chip b { font: 600 12px var(--head); display: block; }
.brand-chip span { font-size: 10px; color: var(--muted); }
.strip {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; background: var(--blue-soft);
  border: 1px solid var(--blue-line); border-radius: 18px; padding: 1.1rem 1.6rem;
}
.strip small { display: block; font: 600 8.5px var(--head); letter-spacing: .12em; color: var(--muted); margin-bottom: .55rem; }
.strip span { font-size: 11.5px; color: var(--navy); }
.section-title { font: 600 21px var(--head); margin: 0; }
.st-key-card_studio h2 { font: 600 26px var(--head); margin: .5rem 0 .3rem; letter-spacing: -.01em; }
.st-key-panel_guide {
  background: var(--blue-tint); border: 1px solid var(--blue-line); border-radius: 16px; padding: 1.1rem 1.2rem;
}
.idea { display: flex; gap: 1rem; align-items: flex-start; }
.idea .n {
  width: 30px; height: 30px; border-radius: 50%; background: var(--navy); color: var(--white);
  display: grid; place-items: center; font: 600 12px var(--head); flex: none;
}
.idea b { font: 600 15px var(--head); display: block; margin: 0 0 .3rem; }
.idea p { font-size: 12px; color: var(--muted); line-height: 1.65; margin: 0; }
.st-key-card_idea { padding: 1.1rem 1.3rem; }
.placeholder { display: flex; gap: 1rem; justify-content: center; align-items: flex-start; padding: 2rem 1rem 1rem; }
.placeholder .ico {
  width: 46px; height: 46px; border-radius: 14px; background: var(--blue-soft); color: var(--navy);
  display: grid; place-items: center; flex: none;
}
.placeholder b { font: 600 13px var(--head); display: block; margin-bottom: .4rem; }
.placeholder span { font-size: 11px; color: var(--muted); line-height: 1.6; display: block; max-width: 22rem; }

.footer {
  display: flex; justify-content: space-between; font-size: 9.5px; color: var(--muted); padding: 2rem 0 0;
}

/* ---------- widgets ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
  background: var(--navy); color: var(--white); border: 1px solid var(--navy); border-radius: 10px;
  font-weight: 600; box-shadow: 0 8px 18px rgba(14, 30, 58, .2); padding: .5rem 1.1rem;
}
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  background: var(--navy-2); border-color: var(--navy-2); color: var(--white);
}
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"] {
  background: var(--white); color: var(--navy); border: 1px solid var(--blue-line); border-radius: 10px; font-weight: 500;
}
[data-testid="stBaseButton-secondary"]:hover { border-color: var(--navy); color: var(--navy); background: var(--blue-soft); }
[data-testid="stBaseButton-tertiary"] { color: var(--navy); background: transparent; border: 0; font-weight: 500; }
[data-testid="stBaseButton-tertiary"]:hover { background: var(--blue-soft); color: var(--navy); }
[data-testid^="stBaseButton"] p { color: inherit; font-size: 12px; }
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p { color: var(--white); }

textarea, [data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="textarea"], [data-baseweb="select"] > div {
  background: var(--white) !important; border-color: var(--blue-line) !important; border-radius: 10px !important;
}
[data-baseweb="input"]:focus-within, [data-baseweb="textarea"]:focus-within, [data-baseweb="select"]:focus-within > div {
  border-color: var(--navy) !important; box-shadow: 0 0 0 3px rgba(91, 164, 230, .25) !important;
}
[data-testid="stWidgetLabel"] p { font: 500 11.5px var(--head); color: var(--black); }
textarea::placeholder, input::placeholder { color: var(--muted) !important; }
[data-testid="stAlert"] { background: var(--blue-soft); color: var(--navy); border: 1px solid var(--blue-line); border-radius: 12px; }
[data-testid="stForm"] { border: 0; padding: 0; }
"""

LOGIN_CSS = (
    """
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] { display: none; }
[data-testid="stMainBlockContainer"] { max-width: none; padding: 0; }
[data-testid="stHorizontalBlock"]:has(.login-left) { gap: 0; min-height: 100vh; align-items: stretch; }
[data-testid="stColumn"]:has(.login-left) { background: var(--navy-deep); }
[data-testid="stColumn"]:has(.login-right) { background: var(--white); }
[data-testid="stColumn"]:has(.login-right) > [data-testid="stVerticalBlock"] {
  width: min(390px, 84%); margin: 0 auto; justify-content: center; min-height: 100vh; gap: .9rem;
}
.login-left {
  min-height: 100vh; padding: 2.4rem 3rem; color: var(--white); position: relative; overflow: hidden;
  display: flex; flex-direction: column; justify-content: space-between;
  background: radial-gradient(circle at 92% 38%, rgba(140, 180, 225, .3), transparent 32%), var(--navy-deep);
}
.login-left .brand-mark { background: var(--blue-soft); color: var(--navy); }
.login-left .brand-name { color: var(--white); }
.login-left .brand-tag { color: rgba(255,255,255,.7); }
.login-left .mid { margin: auto 0; padding-top: 3rem; }
.login-left .eyebrow { color: var(--white); }
.login-left h1 {
  font: 600 clamp(2.8rem, 5.2vw, 4.4rem)/1.03 var(--head) !important; letter-spacing: -.03em;
  color: var(--white) !important; margin: 1.3rem 0 1.4rem;
}
.login-left h1 em { font-style: normal; color: var(--blue-line); }
.login-left .lead { font-size: 12.5px; line-height: 1.7; color: rgba(255,255,255,.92); max-width: 24rem; margin: 0; }
.orbit { position: relative; height: 190px; margin-top: 2.4rem; max-width: 380px; }
.orbit .ring {
  position: absolute; border: 1px solid rgba(255,255,255,.35); border-radius: 50%;
}
.orbit .star { position: absolute; left: 150px; top: 38px; color: var(--white); }
.orbit .note {
  position: absolute; padding: .55rem .9rem; border: 1px solid rgba(255,255,255,.25); border-radius: 12px;
  background: rgba(24, 44, 78, .75); font: 500 10.5px var(--head); display: flex; gap: .5rem; align-items: center;
}
.login-left .foot {
  display: flex; justify-content: space-between; align-items: center; font-size: 10px;
  border-top: 1px solid rgba(255,255,255,.18); padding-top: 1rem;
}
.login-right .top { display: flex; justify-content: space-between; align-items: center; }
.login-right .brand-mark { width: 36px; height: 36px; }
.login-right .eyebrow { margin-top: .6rem; }
.login-right h2 { font: 600 27px var(--head); margin: .5rem 0 .3rem; letter-spacing: -.01em; }
.login-right .lead { font-size: 11.5px; color: var(--muted); line-height: 1.8; margin: 0; }
.login-right .preview { border-top: 1px solid var(--blue-line); padding-top: 1rem; font-size: 10px; color: var(--muted); line-height: 1.7; }
.login-right .preview b { display: block; font: 600 10.5px var(--head); color: var(--navy); margin-bottom: .3rem; }
.st-key-login_email input { padding-left: 2.4rem; background: __MAIL__ no-repeat .8rem center; }
.st-key-login_pw input { padding-left: 2.4rem; background: __LOCK__ no-repeat .8rem center; }
.st-key-fill button { padding: 0; height: auto; min-height: 0; font-size: 11px; }
"""
    .replace("__MAIL__", _input_icon("mail"))
    .replace("__LOCK__", _input_icon("lock"))
)


def _scope(css: str) -> str:
    """Prefix class selectors with .stApp so they beat Streamlit's own element styles."""

    def rule(match: re.Match) -> str:
        selectors = [s.strip() for s in match.group(1).split(",")]
        selectors = [
            f".stApp {s}" if s.startswith((".", "[class")) and not s.startswith(".stApp") else s
            for s in selectors
        ]
        return ",\n".join(selectors) + "{" + match.group(2) + "}"

    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return re.sub(r"([^{}]+)\{([^{}]*)\}", rule, css)


def apply_theme(login: bool = False) -> None:
    css = _scope(CSS + (LOGIN_CSS if login else ""))
    st.markdown(f"<style>{FONTS}\n{css}</style>", unsafe_allow_html=True)
