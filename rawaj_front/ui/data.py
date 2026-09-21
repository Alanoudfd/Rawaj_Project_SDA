"""Front-end data for every Rawaj page.

Everything the UI displays lives here, so the content can be swapped for a real
source later without touching the page code.
"""

from datetime import date

BUSINESS = {
    "name": "3Brews",
    "type": "Food & beverage",
    "city": "Jeddah",
    "audience": "local guests",
    "around": "Your dining experience",
    "voice": "Warm and authentic",
    "language": "English",
}

MONTH = date(2026, 9, 1)

STRATEGY = {
    "north_star": "Encourage more visits to 3Brews",
    "summary": (
        "A 2026-09 content plan for 3Brews in Jeddah. Focus on encourage "
        "more visits to 3brews for local guests, using a Warm and authentic tone."
    ),
    "pillars": [
        {
            "title": "Menu discovery",
            "text": "Help local guests discover the current food menu at 3Brews.",
            "signal": "Menu questions and post saves",
        },
        {
            "title": "At the table",
            "text": "Show the real meal preparation and dining atmosphere at 3Brews.",
            "signal": "Reel views and profile visits",
        },
        {
            "title": "Guest connections",
            "text": (
                "Start a conversation with local guests in Jeddah to support: "
                "Encourage more visits to 3Brews."
            ),
            "signal": "Story replies and visit enquiries",
        },
    ],
    "focus_title": "Let people experience 3Brews before they visit.",
    "focus_text": (
        "Show the people, products, and experience that make your place recognizable."
    ),
    "focus_points": [
        "Your voice: Warm and authentic",
        "Keep every post connected to your profile",
    ],
}

# One calendar task per planned day: (day, format, title, description)
_TASKS = [
    (1, "Reel", "Meet 3Brews", "Introduce 3Brews and its meals and the dining experience to local guests."),
    (4, "Post", "Signature dish spotlight", "Give one signature dish its own moment, with a close-up and a simple reason to try it."),
    (6, "Story", "Behind the counter", "Share a quick look at how a meal is prepared before it reaches the table."),
    (9, "Reel", "From kitchen to table", "Follow one order from the pass to the table in a short, warm walkthrough."),
    (12, "Post", "Menu favourites", "Show the three dishes guests order most and let the food do the talking."),
    (14, "Story", "Ask our guests", "Open a question box so guests can ask what to order on their first visit."),
    (17, "Reel", "A table for the weekend", "Set the scene for a relaxed weekend meal with friends and family."),
    (19, "Post", "Seasonal special", "Introduce a seasonal plate with a clear invitation to visit this week."),
    (22, "Story", "National Day countdown", "A light countdown that points guests toward dining with you on the holiday."),
    (25, "Reel", "Weekend at 3Brews", "Capture the atmosphere of a busy evening: the sounds, the plates, the people."),
    (27, "Post", "Guest moments", "Feature a real guest moment (with permission) to show the room feels welcoming."),
    (30, "Story", "Month in review", "Look back at the month's favourite dishes and invite guests to what's next."),
]

TASKS = [
    {
        "date": MONTH.replace(day=day),
        "format": fmt,
        "title": title,
        "text": text,
        "status": "Planned",
    }
    for day, fmt, title, text in _TASKS
]
