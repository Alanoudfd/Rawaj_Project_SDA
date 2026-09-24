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
- `ui/api.py`            HTTP client for the FastAPI backend
- `ui/theme.py`          all CSS: colors (navy / light blue / white / black) and fonts
- `ui/components.py`     sidebar, top bar, page header, footer; resolves the owner's restaurant
- `ui/icons.py`          inline SVG icons
- `ui/data.py`           sample data for the Strategy and Content pages (not connected yet)
- `.streamlit/config.toml` light theme, hides Streamlit's default page nav

## Home page
The workspace belongs to one restaurant (no picker): `RAWAJ_RESTAURANT_ID` if set, else the restaurant
whose email matches the sign-in email, else the first one. `GET /api/restaurants/{id}/gaps` returns the
latest marketing gaps with counts per severity (High / Moderate / Low) and data limitations.
The page re-reads the API every 5 seconds.
