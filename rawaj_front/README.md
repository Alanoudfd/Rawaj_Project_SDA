# Rawaj front-end (Streamlit)

Talks to the Rawaj backend **only through the FastAPI API** (no direct database access).

Start the backend from the project root, then the front-end:

    uvicorn api.main:app --reload            # http://127.0.0.1:8000
    cd rawaj_front
    pip install -r requirements.txt
    streamlit run app.py

Set `RAWAJ_API_URL` if the backend is not on `http://127.0.0.1:8000`.

## Files
- `app.py`               entry point: page setup, sign-in gate, navigation
- `views/`               the 4 pages (login, home, strategy, content)
- `ui/workspace.py`      the post workspace shown under the chosen idea on the Content page (facts, kit, preview, upload, ending)
- `ui/post_kit.py`       the workspace's logic (caption fold, subject check, photo check, preview, progress bar), no Streamlit
- `ui/api.py`            HTTP client for the FastAPI backend
- `ui/theme.py`          all CSS: colors (navy / light blue / white / black) and fonts
- `ui/components.py`     sidebar, top bar, page header, footer; resolves the owner's restaurant
- `ui/icons.py`          inline SVG icons
- `ui/data.py`           sample data for the Strategy and Content pages (not connected yet)
- `.streamlit/config.toml` light theme, hides Streamlit's default page nav

## Content page and post workspace
One page. The owner picks a day, generates ideas and chooses one ("Not the right idea? Choose another" reopens the ideas);
the workspace then appears under the chosen idea and turns it into a post that can be carried out in minutes:

- **Progress bar**: Idea selected, Kit ready, Content uploaded, Scheduled, Published, Measured. The last two are dashed:
  Rawaj is meant to complete them by itself once it can see Instagram.
- **Why this post**: the marketing gap (from the saved strategy) that the idea answers.
- **Confirm the facts**: an idea is not always one dish, so a small model step reads the chosen idea
  (`POST .../post-kit/facts-plan`) and the form asks only for what it needs: item rows (English and Arabic name, price, and a
  moment or group for a menu-by-moment post), the ways guests can get the food (visit, pickup, Jahez...), an offer and a note
  for other details. Names the idea itself gives are pre-filled for the owner to confirm; prices are never guessed. Plus the
  caption language and whether a photo exists. If the model cannot be reached the general form is shown. The kit only uses
  these facts: an empty price, offer or way to order means none is mentioned.
- **Post kit** (written by the model, `POST /api/restaurants/{id}/agent-strategy/days/{day}/post-kit`):
  - *Caption*: written automatically with the hashtags as soon as the facts are ready (no button). One caption, not
    three: the owner picks its tone (Warm, Playful, Premium, Direct) and the caption is rewritten in the edit box straight away;
    chips make one change (Shorter, Stronger hook). It ends with an interaction prompt, and a live check says that an item
    (or way to order) is named before Instagram's "more". If the idea's own names do not fill the form yet, the owner fills
    it in and presses "Write my caption".
  - *Shoot*: a phone-friendly guide for the format (a hook for the first 2 seconds and scenes for a Reel; angle, lighting and
    composition for a single image; slides for a carousel; frames for a Story) and a checklist.
  - *Look*: cover frame, optional text overlay, crop rules, and the owner's own brand colours (Rawaj does not guess them).
  - *Publish*: the best time to post (computed from the account's own posts, in Riyadh time, never by the model), the location tag,
    suggested mentions (only handles the account has already used) and follow-up ideas such as a Story poll.
- **Live preview**: an Instagram-style post that follows the edits, folds the caption at "more" and crops the picture like Instagram.
- **Upload**: a photo or video shows in the preview. A photo also gets a basic check of size, shape and light (pixels only, no AI).
  The upload is kept for the session only.
- **Ending**: copy the caption, hashtags, shot list or the whole kit; the card says plainly that Rawaj does not post for the owner.
  **Mark as posted** completes the day on the calendar (strategy progress moves) and offers the next task; **Undo** reverses it.
  Optionally the owner adds the post link and answers "How did it go?". That answer is the owner's own read, not a measurement.

The kit, the edits and the choices are kept for the session, per restaurant, day and idea (like the content ideas). Marking a day
as posted, the link and the answer are saved by the API. Generating a kit needs `OPENAI_API_KEY`, like the content ideas.

## Home page
The workspace belongs to one restaurant (no picker): `RAWAJ_RESTAURANT_ID` if set, else the restaurant
whose email matches the sign-in email, else the first one. `GET /api/restaurants/{id}/gaps` returns the
latest marketing gaps with counts per severity (High / Moderate / Low) and data limitations.
The page re-reads the API every 5 seconds.
