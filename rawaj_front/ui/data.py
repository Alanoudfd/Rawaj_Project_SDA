"""Front-end data for every Rawaj page.

Everything the UI displays lives here, so the content can be swapped for a real
source later without touching the page code.
"""

from datetime import date

BUSINESS = {
    "name": "3Brews",
    "type": "Restaurant",
    "city": "Jeddah",
    "audience": "local guests",
    "around": "Your dining experience",
    "voice": "Warm and authentic",
    "language": "English",
}

MONTH = date(2026, 9, 1)

STRATEGY = {
    "north_star": "Encourage more dining visits to 3Brews",
    "summary": (
        "A 2026-09 content plan for 3Brews, a restaurant in Jeddah. Focus on encourage "
        "more dining visits to 3brews for local guests, using a Warm and authentic tone."
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
                "Encourage more dining visits to 3Brews."
            ),
            "signal": "Story replies and visit enquiries",
        },
    ],
    "focus_title": "Let people experience 3Brews before they visit.",
    "focus_text": (
        "Show the people, products, and experience that make your restaurant recognizable."
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

_IDEA_ANGLES = {
    "Reel": [
        ("One dish, one story", "Film a single dish from prep to first bite in under 20 seconds, with the sound of the kitchen."),
        ("The first thing you notice", "Open on the moment a plate lands on the table, then cut to a guest's reaction."),
        ("Come hungry", "A quick tour of the room and the menu ending with a simple invitation to book a table."),
    ],
    "Post": [
        ("The close-up", "A single bright, well-lit photo of the dish with a short caption on why guests love it."),
        ("Three things to try", "A carousel of three favourites with a one-line description each and a save-for-later prompt."),
        ("Table for two", "A warm lifestyle photo of the dining room with a gentle invitation to visit this week."),
    ],
    "Story": [
        ("Ask us anything", "Use a question box so guests can ask what to order, then answer with short clips."),
        ("This or that", "A two-option poll between favourite dishes that starts a conversation."),
        ("Today at 3Brews", "A three-frame story: the room before service, the first plate out, and today's welcome."),
    ],
}


def generate_ideas(task: dict, guidance: str = "") -> list[dict]:
    """Return three content ideas for a calendar task (front-end sample logic)."""
    angles = _IDEA_ANGLES.get(task["format"], _IDEA_ANGLES["Post"])
    ideas = []
    for title, text in angles:
        if guidance.strip():
            text = f"{text} Shaped by your note: {guidance.strip()}"
        ideas.append({"title": title, "format": task["format"], "text": text})
    return ideas
