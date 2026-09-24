"""Client for the Rawaj FastAPI backend.

The front-end never touches the database: every value on screen comes from the API.
Set RAWAJ_API_URL if the backend is not on http://127.0.0.1:8000.
"""

import os

import requests

API_URL = os.getenv("RAWAJ_API_URL", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = 5
IDEAS_TIMEOUT = 75  # the model writes the ideas, which takes longer than a database read


class ApiError(Exception):
    """The backend could not be reached or answered with an error."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _request(method: str, path: str, body: dict | None = None, timeout: int = TIMEOUT):
    try:
        response = requests.request(method, f"{API_URL}/api{path}", json=body, timeout=timeout)
    except requests.RequestException as exc:
        raise ApiError(f"Could not reach the Rawaj API at {API_URL}: {exc}") from exc
    if not response.ok:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = None
        raise ApiError(f"{method} {path} failed (HTTP {response.status_code}): {detail or response.reason}", response.status_code)
    if response.status_code == 204 or not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError(f"{method} {path} returned a non-JSON response") from exc


def list_restaurants() -> list[dict]:
    return _request("GET", "/restaurants?limit=100")["items"]


def get_gaps(restaurant_id: int) -> dict:
    """Marketing gaps of the latest completed qualification, with counts per severity."""
    return _request("GET", f"/restaurants/{restaurant_id}/gaps")


def get_agent_strategy(restaurant_id: int) -> dict | None:
    """The Strategy Agent's 30-day strategy, or None if it has not produced one yet."""
    try:
        return _request("GET", f"/restaurants/{restaurant_id}/agent-strategy")
    except ApiError as exc:
        if exc.status == 404:
            return None
        raise


def set_day_status(restaurant_id: int, day: int, status: str) -> dict:
    return _request("PATCH", f"/restaurants/{restaurant_id}/agent-strategy/days/{day}", {"status": status})


def login(username: str, password: str) -> dict:
    """{"role": "owner" | "admin", "username", "restaurant_id"}; ApiError(status=401) if wrong."""
    return _request("POST", "/auth/login", {"username": username, "password": password})


def get_day_ideas(restaurant_id: int, day: int, previous_ideas: list[dict] | None = None, feedback: str = "") -> list[dict]:
    """Three content ideas for one day of the strategy. Send the ideas already shown to get different ones."""
    body = {"previous_ideas": previous_ideas or [], "feedback": feedback}
    return _request("POST", f"/restaurants/{restaurant_id}/agent-strategy/days/{day}/ideas", body, timeout=IDEAS_TIMEOUT)["ideas"]
