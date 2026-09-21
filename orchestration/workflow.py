"""The Rawaj pipeline: every agent, in one LangGraph.

    START ─┬─ analyze ────►  research ─► qualification ─► outreach ─► END
           │                 (Instagram)   (gaps, decision)  (email 1 draft; the email is reviewed
           │                                                  by a second model and then sent)
           │
           ├─ strategy_inbox ► strategy ─► notify_client ─► END
           │                   (after the restaurant clicked "Interested": 30-day plan, told that
           │                    the restaurant is interested)      (email 2: sign-in + dashboard link)
           │
           ├─ send_emails ──► send_emails ─► END     (sends the emails that passed the review)
           │
           └─ followups ────► followups ─► END       (restaurants that did not answer)

One graph, several entry points: `analyze` runs when someone starts an analysis; the others run when
something happens (a click, a timer). The graph never waits inside a run for the restaurant: the
restaurant's click is what starts `strategy_inbox` later.

The only human in the loop is the restaurant. An email is sent when the review model marked it
`passed` and `privacy_safe`, it is a routine type and an email provider is configured.

Public functions (each one invokes the graph with the matching event):
    run_restaurant_workflow(...)   analyze
    run_strategy_stage(...)        strategy_inbox
    send_reviewed_emails(...)      send_emails
    run_followups(...)             followups

Agents are imported inside the nodes, so importing this module needs no API keys. See WORKFLOW.md.
"""

import json
import logging
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agents.qualification_agent.prompt import QUALIFICATION_PROMPT_VERSION
from agents.research_agent.research_models import RestaurantInfo
from database.database import SessionLocal
from database.models import OutboundMessage, QualificationRun, ResearchRun, Restaurant, Strategy
from database.repository import (
    build_qualification_input,
    get_latest_research,
    get_qualification_for_research,
    save_qualification_result,
    save_research_result,
)
from orchestration.outreach_node import outreach_node

logger = logging.getLogger(__name__)


# =========================================================
# STATE
# =========================================================


class PipelineState(TypedDict, total=False):
    event: Literal["analyze", "strategy_inbox", "send_emails", "followups"]

    # analyze: input
    request: dict[str, Any]
    # analyze: output
    restaurant_id: int
    research_run_id: int
    qualification_run_id: int
    qualification_result: dict[str, Any]
    outreach: dict[str, Any]
    error: str

    # strategy_inbox
    limit: int
    strategy_summary: dict[str, Any]
    strategy_saved: list[dict[str, Any]]
    notifications: list[dict[str, Any]]

    # send_emails / followups
    email_summary: dict[str, Any]
    followup_summary: dict[str, Any]


def _settings(config: RunnableConfig) -> dict[str, Any]:
    """Things a caller injects for one run (database sessions, fakes in tests): see the public functions."""
    return (config or {}).get("configurable", {})


REVIEW_ATTEMPTS = 3


def _write_until_reviewed(call: Callable[[], dict[str, Any]], attempts: int = REVIEW_ATTEMPTS) -> dict[str, Any]:
    """Run an Outreach step that writes an email; if the review model rejects the wording, write it again.

    The review model is strict and its verdict varies between runs. The same request can simply be run again:
    it produces new wording, and only an email that passes the review is ever sent.
    """
    outcome = call()
    for _ in range(attempts - 1):
        errors = " ".join(str(error) for error in outcome.get("outreach_errors") or [])
        if outcome.get("outreach_pending_human_approval") or "review did not pass" not in errors:
            break
        logger.info("The review model rejected the email; writing it again.")
        outcome = call()
    return outcome


def _online(check: str, *args) -> None:
    """Score what an agent just produced with the checks written in code, in LangSmith (evals/online.py).

    Needs LangSmith tracing; costs nothing; never affects the pipeline."""
    try:
        from evals import online

        getattr(online, check)(*args)
    except Exception as error:
        logger.debug("Online check %s skipped (%s)", check, type(error).__name__)


def _default_application():
    """The Outreach Agent runtime, wired to create the client's dashboard account for email 2."""
    from agents.outreach_followup_agent.agent import RawajOutreachApplication
    from api import accounts

    return RawajOutreachApplication.create(access_provider=accounts.provision_access)


# =========================================================
# ANALYZE: research
# =========================================================


def research_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    request = state["request"]
    restaurant_id = request["restaurant_id"]
    content_limit, lookback_days = request["content_limit"], request["lookback_days"]

    with _settings(config)["session_factory"]() as db:
        restaurant = db.get(Restaurant, restaurant_id)
        if restaurant is None:
            return {"error": "Restaurant not found."}

        research_run = None
        if not request["force_refresh"]:
            research_run = get_latest_research(
                db, restaurant_id, content_limit=content_limit, lookback_days=lookback_days,
            )

        if research_run is None:
            try:
                restaurant_input = RestaurantInfo(
                    restaurant_id=restaurant.id,
                    name=restaurant.name,
                    instagram_username=restaurant.instagram_username,
                    instagram_url=(
                        restaurant.instagram_url
                        or f"https://www.instagram.com/{restaurant.instagram_username.strip('@')}"
                    ),
                    email=restaurant.email,
                    location=restaurant.location,
                )
                from agents.research_agent.research_agent import run_research_agent

                research_report = run_research_agent(
                    restaurant=restaurant_input, content_limit=content_limit, lookback_days=lookback_days,
                )
                research_run = save_research_result(
                    db=db,
                    restaurant_id=restaurant.id,
                    result=research_report.model_dump(mode="json"),
                    content_limit=content_limit,
                    lookback_days=lookback_days,
                )
            except Exception:
                logger.error("Research failed for restaurant %s. Please try again.", restaurant_id)
                return {"restaurant_id": restaurant_id, "error": "Research failed. Please try again."}

        if str(getattr(research_run, "status", "")).lower() == "failed":
            return {
                "restaurant_id": restaurant_id,
                "research_run_id": research_run.id,
                "error": "Research failed. Please try again.",
            }
        if research_run.full_result:
            _online("check_research", research_run.full_result)
        return {"restaurant_id": restaurant_id, "research_run_id": research_run.id}


# =========================================================
# ANALYZE: qualification
# =========================================================


def _context_compatible(existing_context: Any, requested_context: Any) -> bool:
    previous = existing_context if isinstance(existing_context, dict) else {}
    current = requested_context if isinstance(requested_context, dict) else {}
    return previous == current


def qualification_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    request = state["request"]
    restaurant_id, restaurant_context = state["restaurant_id"], request["context"]

    with _settings(config)["session_factory"]() as db:
        research_run = db.get(ResearchRun, state["research_run_id"])

        existing = get_qualification_for_research(db, research_run.id)
        previous_context = existing.full_result.get("restaurant_context") or {} if existing is not None else {}
        current_version = existing is not None and (
            existing.full_result.get("prompt_version") == QUALIFICATION_PROMPT_VERSION
        )
        if existing and current_version and _context_compatible(previous_context, restaurant_context):
            return {"qualification_run_id": existing.id, "qualification_result": existing.full_result}

        try:
            qualification_input = build_qualification_input(research_run)
            qualification_input["restaurant_context"] = deepcopy(restaurant_context)
            qualification_input["analysis_coverage"] = (
                research_run.analysis_coverage or {"content_requested": request["content_limit"]}
            )
            qualification_input["data_quality"] = research_run.data_quality or {}

            from agents.qualification_agent.qualification_agent import run_qualification_agent

            qualification_result = run_qualification_agent(qualification_input)
            qualification_result["restaurant_context"] = deepcopy(restaurant_context)
            qualification_result["prompt_version"] = QUALIFICATION_PROMPT_VERSION
            qualification_run = save_qualification_result(
                db=db,
                restaurant_id=restaurant_id,
                research_run_id=research_run.id,
                result=qualification_result,
            )
            _online("check_qualification", qualification_result, qualification_input)
            return {"qualification_run_id": qualification_run.id, "qualification_result": qualification_result}
        except Exception:
            logger.error("Qualification failed for restaurant %s. Please try again.", restaurant_id)
            return {"error": "Qualification failed. Please try again."}


# =========================================================
# ANALYZE: outreach (email 1)
# =========================================================


def outreach_stage_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Hand the exact Research/Qualification runs to the Outreach Agent, which drafts email 1.

    The email is then reviewed by a second model and sent by `send_emails`. A problem in this stage is
    reported in the result but never turns a finished analysis into a failed one.
    """
    if not state["request"]["start_outreach"]:
        return {}
    settings = _settings(config)
    restaurant_id = state["restaurant_id"]

    with settings["session_factory"]() as db:
        restaurant = db.get(Restaurant, restaurant_id)
        has_email = bool(restaurant and restaurant.email)
    if not has_email:
        return {"outreach": {"status": "SKIPPED_NO_EMAIL"}}

    response = _write_until_reviewed(lambda: outreach_node(
        {
            "restaurant_id": restaurant_id,
            "research_run_id": state["research_run_id"],
            "qualification_run_id": state["qualification_run_id"],
        },
        outreach_runner=settings.get("outreach_runner"),
    ))
    if response.get("error"):
        logger.error("Outreach did not start for restaurant %s: %s", restaurant_id, response["error"])
        return {"outreach": {"status": "ERROR", "error": response["error"]}}
    if response.get("outreach_action") == "SEND_INITIAL_OUTREACH" and response.get("outreach_message_id"):
        with settings["session_factory"]() as db:
            message = db.get(OutboundMessage, response["outreach_message_id"])
            restaurant = db.get(Restaurant, restaurant_id)
            if message and restaurant:
                _online("check_first_email", message.plain_text_body, restaurant.name)
    return {
        "outreach": {
            "status": response.get("outreach_status"),
            "action": response.get("outreach_action"),
            "thread_id": response.get("outreach_thread_id"),
            "message_id": response.get("outreach_message_id"),
            "pending_human_approval": response.get("outreach_pending_human_approval", False),
            "errors": response.get("outreach_errors", []),
        }
    }


# =========================================================
# STRATEGY (after "Interested") and email 2
# =========================================================


def strategy_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Turn every pending Strategy request (written when a restaurant clicked "Interested") into a strategy.

    The Strategy Agent is told the restaurant is interested, drafts the 30-day plan, self-reflects, passes
    the guardrails and is saved. A request without a verified Interested event is refused.
    """
    process = _settings(config).get("strategy_process")
    if process is None:
        from agents.strategy_agent.strategy_worker import process_strategy_requests_once as process

    summary = process(limit=state.get("limit", 10))
    _online("check_strategy_handoff", summary)
    saved = [item for item in summary.get("items", []) if item.get("status") == "STRATEGY_GENERATED_AND_SAVED"]
    for item in saved:
        _score_saved_strategy(item["strategy_id"])
    return {"strategy_summary": summary, "strategy_saved": saved}


def _score_saved_strategy(strategy_id: int) -> None:
    """Online evaluation of a strategy that was just saved (only when LangSmith tracing is on)."""
    if os.getenv("LANGSMITH_TRACING", "").strip().lower() not in {"true", "1"}:
        return
    try:
        with SessionLocal() as db:
            strategy = db.get(Strategy, strategy_id)
            if strategy is None:
                return
            data = dict(strategy.strategy_data or {})
            run = db.get(QualificationRun, strategy.qualification_run_id) if strategy.qualification_run_id else None
            qualification = run.full_result if run else None
        _online("check_strategy", data, qualification, data.get("strategy_start_date"))
    except Exception as error:
        logger.debug("Online check of the strategy skipped (%s)", type(error).__name__)


def dashboard_url() -> str:
    """Where the client reads the strategy (the Streamlit front-end unless DASHBOARD_URL says otherwise)."""
    return os.getenv("DASHBOARD_URL", "http://localhost:8501").rstrip("/") + "/strategy"


def build_strategy_output(request: dict[str, Any], strategy_id: int, strategy_data: dict[str, Any]) -> dict[str, Any]:
    """The Outreach Agent's StrategyOutputHandoff for a saved strategy, with only client-safe content."""
    from agents.outreach_followup_agent.schemas import StrategyOutputHandoff, StrategyOutputStatus

    targets = [str(t).strip() for t in strategy_data.get("thirty_day_target") or [] if str(t).strip()]
    services = [
        str(item["service"]).strip()
        for item in strategy_data.get("recommended_services") or []
        if isinstance(item, dict) and item.get("service")
    ]
    summary = "Your 30-day marketing plan is ready."
    if targets:
        summary += " It focuses on: " + "; ".join(targets) + "."
    return StrategyOutputHandoff(
        strategy_id=strategy_id,
        strategy_request_id=request["strategy_request_id"],
        restaurant_id=request["restaurant_id"],
        status=StrategyOutputStatus.READY,
        dashboard_strategy_url=dashboard_url(),
        client_notification_allowed=True,
        client_safe_summary=summary,
        client_safe_deliverables=services,
        completed_at=datetime.now(timezone.utc).isoformat(),
    ).model_dump(mode="json")


def notify_strategy_ready(saved: dict[str, Any], *, application=None) -> dict[str, Any]:
    """Give a saved strategy to the Outreach Agent, which drafts email 2 (sign-in details + dashboard link)."""
    from agents.outreach_followup_agent.agent import receive_strategy_agent_output

    with SessionLocal() as db:
        strategy = db.get(Strategy, saved["strategy_id"])
        strategy_data = dict(strategy.strategy_data or {}) if strategy else {}
    output = build_strategy_output(saved, saved["strategy_id"], strategy_data)
    return receive_strategy_agent_output(output, application=application)


def _notify_dir() -> Path:
    from agents.outreach_followup_agent.config import get_settings

    return Path(get_settings().strategy_handoff_outbox).parent / "notify"


def notify_client_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Email 2 for every strategy just saved, plus any earlier notification that failed.

    A failed notification is kept in a small outbox and retried on the next pass, so the strategy is
    never generated a second time just because an email step failed.
    """
    settings = _settings(config)
    send = settings.get("notify") or (
        lambda saved: notify_strategy_ready(saved, application=(settings.get("application_factory") or _default_application)())
    )
    notify = lambda saved: _write_until_reviewed(lambda: send(saved))
    notify_dir = settings.get("notify_dir") or _notify_dir()

    results = []
    for path in sorted(notify_dir.glob("*.json")) if notify_dir.exists() else []:
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            results.append({"strategy_request_id": saved["strategy_request_id"], "notification": notify(saved)})
            path.unlink()
        except Exception as error:
            logger.error("Strategy-ready notification retry failed for %s: %s", path.name, error)
            results.append({"request_file": path.name, "notification": f"FAILED: {error}"})

    for item in state.get("strategy_saved", []):
        saved = {key: item[key] for key in ("strategy_request_id", "restaurant_id", "strategy_id")}
        try:
            results.append({**saved, "notification": notify(saved)})
        except Exception as error:
            notify_dir.mkdir(parents=True, exist_ok=True)
            (notify_dir / f"{saved['strategy_request_id']}.json").write_text(json.dumps(saved), encoding="utf-8")
            logger.error("Strategy-ready notification failed; will retry: %s", error)
            results.append({**saved, "notification": f"PENDING_RETRY: {error}"})
    return {"notifications": results}


# =========================================================
# SENDING: emails that passed the review
# =========================================================

EMAIL_APPROVAL = "HUMAN_EMAIL_APPROVAL_REQUIRED"
AUTO_APPROVED_TYPES = {"INITIAL_OUTREACH", "NO_RESPONSE_FOLLOW_UP", "STRATEGY_READY_NOTIFICATION"}
AUTO_REVIEWER_ID = "auto:ai-review"
_email_lock = threading.Lock()
_warned_no_provider = False


def auto_send_enabled() -> bool:
    return os.getenv("AUTO_APPROVE_EMAILS", "true").strip().lower() not in {"0", "false", "no", "off"}


def paused_email_requests(application) -> list[dict[str, Any]]:
    """Interrupt payloads of every Outreach run that is paused before sending an email."""
    outreach = application.workflow
    thread_ids: list[str] = []
    for item in outreach.checkpointer.list(None):
        thread_id = item.config["configurable"]["thread_id"]
        if thread_id not in thread_ids:
            thread_ids.append(thread_id)
    found = []
    for thread_id in thread_ids:
        state = outreach.graph.get_state({"configurable": {"thread_id": thread_id}})
        for task in state.tasks:
            for interrupt in task.interrupts:
                value = interrupt.value
                if isinstance(value, dict) and value.get("type") == EMAIL_APPROVAL:
                    found.append({**value, "thread_id": thread_id})
    return found


def _not_sendable_reason(request: dict[str, Any]) -> str | None:
    """None when the email may be sent automatically, else why not."""
    review = request.get("review") if isinstance(request.get("review"), dict) else {}
    if request.get("message_type") not in AUTO_APPROVED_TYPES:
        return f"{request.get('message_type')} emails are not sent automatically"
    if review.get("passed") is not True or review.get("privacy_safe") is not True:
        return "the content review did not pass"
    return None


def send_emails_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Approve, on the agent's behalf, every paused email whose review passed; the agent then sends it.

    All must hold: the review marked it `passed` and `privacy_safe`; it is a routine type (a reply about a
    client's complaint, for example, stays paused); an email provider is configured; AUTO_APPROVE_EMAILS is
    not switched off. Safe to run repeatedly and from several threads.
    """
    global _warned_no_provider
    if not auto_send_enabled():
        return {"email_summary": {"enabled": False, "approved": [], "skipped": []}}

    with _email_lock:
        application = (_settings(config).get("application_factory") or _default_application)()
        outreach_settings = application.settings
        if not (outreach_settings.email_provider and outreach_settings.from_email):
            waiting = paused_email_requests(application)
            if waiting and not _warned_no_provider:  # once, not on every sweep
                logger.warning(
                    "%s email(s) are waiting but no email provider is configured (EMAIL_PROVIDER, FROM_EMAIL); nothing is sent.",
                    len(waiting),
                )
                _warned_no_provider = True
            return {"email_summary": {"enabled": True, "approved": [], "skipped": [], "reason": "email provider not configured"}}
        _warned_no_provider = False

        approved, skipped = [], []
        for request in paused_email_requests(application):
            reason = _not_sendable_reason(request)
            if reason:
                skipped.append({"message_id": request["message_id"], "reason": reason})
                continue
            try:
                result = application.workflow.resume_human_approval(
                    thread_id=request["thread_id"],
                    reviewer_id=AUTO_REVIEWER_ID,
                    decision="APPROVED",
                    note="Approved automatically: the content review passed.",
                    message_id=request["message_id"],
                    message_revision=request["message_revision"],
                    content_sha256=request["content_sha256"],
                )
                approved.append({
                    "message_id": request["message_id"], "message_type": request["message_type"],
                    "errors": list(result.errors or []),
                })
            except Exception as error:
                logger.error("Automatic approval of %s failed (%s)", request["message_id"], type(error).__name__)
                skipped.append({"message_id": request["message_id"], "reason": f"approval failed: {type(error).__name__}"})
        summary = {"enabled": True, "approved": approved, "skipped": skipped}
        _online("check_emails_sent", summary)
        return {"email_summary": summary}


# =========================================================
# FOLLOW-UPS
# =========================================================


def followups_node(state: PipelineState, config: RunnableConfig) -> dict[str, Any]:
    """Draft follow-ups for restaurants that did not answer and client check-ins (sent by `send_emails`)."""
    application = (_settings(config).get("application_factory") or _default_application)()
    limit = state.get("limit", 100)
    prospects = application.scheduler.run_due_followups_once(limit=limit)
    clients = application.scheduler.run_due_client_checks_once(limit=limit)
    return {
        "followup_summary": {
            "prospects": {"scanned": prospects.scanned, "started": prospects.started},
            "clients": {"scanned": clients.scanned, "started": clients.started},
        }
    }


# =========================================================
# GRAPH
# =========================================================


def route_event(state: PipelineState) -> str:
    return state["event"]


def stop_on_error(next_node: str) -> Callable[[PipelineState], str]:
    return lambda state: "end" if state.get("error") else next_node


workflow = StateGraph(PipelineState)
workflow.add_node("research", research_node)
workflow.add_node("qualification", qualification_node)
workflow.add_node("outreach", outreach_stage_node)
workflow.add_node("strategy", strategy_node)
workflow.add_node("notify_client", notify_client_node)
workflow.add_node("send_emails", send_emails_node)
workflow.add_node("followups", followups_node)

workflow.add_conditional_edges(
    START,
    route_event,
    {"analyze": "research", "strategy_inbox": "strategy", "send_emails": "send_emails", "followups": "followups"},
)
workflow.add_conditional_edges("research", stop_on_error("qualification"), {"qualification": "qualification", "end": END})
workflow.add_conditional_edges("qualification", stop_on_error("outreach"), {"outreach": "outreach", "end": END})
workflow.add_edge("outreach", END)
workflow.add_edge("strategy", "notify_client")
workflow.add_edge("notify_client", END)
workflow.add_edge("send_emails", END)
workflow.add_edge("followups", END)

graph = workflow.compile()


# =========================================================
# PUBLIC API
# =========================================================


def run_restaurant_workflow(
    restaurant_id: int,
    content_limit: int = 30,
    lookback_days: int = 90,
    *,
    context: dict[str, Any] | None = None,
    force_refresh: bool = False,
    session_factory=None,
    start_outreach: bool = False,
    outreach_runner=None,
):
    """Analyze one restaurant: research -> qualification -> (optionally) outreach."""
    if not isinstance(restaurant_id, int) or isinstance(restaurant_id, bool) or restaurant_id <= 0:
        raise ValueError("restaurant_id must be a positive integer")

    if not isinstance(content_limit, int) or isinstance(content_limit, bool) or not 1 <= content_limit <= 100:
        raise ValueError("content_limit must be between 1 and 100")

    if not isinstance(lookback_days, int) or isinstance(lookback_days, bool) or not 1 <= lookback_days <= 365:
        raise ValueError("lookback_days must be between 1 and 365")

    if not isinstance(force_refresh, bool):
        raise ValueError("force_refresh must be a boolean")

    if context is None:
        context = {}
    if not isinstance(context, dict):
        raise ValueError("context must be a dictionary")

    final = graph.invoke(
        {
            "event": "analyze",
            "request": {
                "restaurant_id": restaurant_id,
                "content_limit": content_limit,
                "lookback_days": lookback_days,
                "context": deepcopy(context),
                "force_refresh": force_refresh,
                "start_outreach": start_outreach,
            },
        },
        {"configurable": {"session_factory": session_factory or SessionLocal, "outreach_runner": outreach_runner}},
    )
    keys = ("restaurant_id", "research_run_id", "qualification_run_id", "qualification_result", "outreach", "error")
    return {key: final[key] for key in keys if key in final}


def run_strategy_stage(limit: int = 10, *, strategy_process=None, notify=None, notify_dir=None, application_factory=None) -> dict:
    """Strategy for every restaurant that clicked "Interested", then email 2 to the client."""
    final = graph.invoke(
        {"event": "strategy_inbox", "limit": limit},
        {"configurable": {
            "strategy_process": strategy_process, "notify": notify, "notify_dir": notify_dir,
            "application_factory": application_factory,
        }},
    )
    return {**final.get("strategy_summary", {}), "notifications": final.get("notifications", [])}


def send_reviewed_emails(application_factory=None) -> dict:
    """Send the emails that passed the review."""
    final = graph.invoke({"event": "send_emails"}, {"configurable": {"application_factory": application_factory}})
    return final["email_summary"]


def run_followups(limit: int = 100, application_factory=None) -> dict:
    """Draft the due follow-ups."""
    final = graph.invoke({"event": "followups", "limit": limit}, {"configurable": {"application_factory": application_factory}})
    return final["followup_summary"]


# =========================================================
# START SYSTEM
# =========================================================


def run_workflow():
    db = SessionLocal()

    try:
        restaurants = db.query(Restaurant).filter(Restaurant.is_active == True).all()
        restaurant_jobs = [{"id": restaurant.id, "name": restaurant.name} for restaurant in restaurants]
    finally:
        db.close()

    if not restaurant_jobs:
        print("No active restaurants found in the database.")
        return

    print(f"\nFound {len(restaurant_jobs)} active restaurant(s).\n")

    for restaurant in restaurant_jobs:
        print("=" * 60)
        print(f"Processing: {restaurant['name']} (ID: {restaurant['id']})")
        print("=" * 60)

        result = run_restaurant_workflow(restaurant["id"])
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            print()
            continue

        print("Research Run ID:", result.get("research_run_id"))
        print("Qualification Run ID:", result.get("qualification_run_id"))
        qualification_result = result.get("qualification_result", {})
        print("Qualification:", qualification_result.get("qualification"))
        print()


if __name__ == "__main__":
    run_workflow()
