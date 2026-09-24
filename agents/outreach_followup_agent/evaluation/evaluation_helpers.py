"""Small evaluation targets. No production database writes or real email delivery."""
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

# Reuse the existing isolated infrastructure, not a second implementation of the agent.
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tests"))
from test_workflow_offline import WorkflowOfflineTests
from agents.outreach_followup_agent.schemas import ButtonClickEvent, ButtonAction, StrategyOutputHandoff
from agents.outreach_followup_agent.llm_service import RawajLLMService
from agents.outreach_followup_agent.config import get_settings
from agents.outreach_followup_agent.guardrails import safe_preview

IDS = dict(restaurant_id=1, research_run_id=101, qualification_run_id=202)

def action_target(inputs):
    # Actual SQL repository proves the transactional opt-out, in an isolated in-memory DB.
    from test_team_repository_integration import TeamRepositoryIntegrationTests
    seed = TeamRepositoryIntegrationTests()
    seed.setUp()
    try:
        return _action_target(inputs, seed)
    finally:
        seed.tearDown()

def _action_target(inputs, seed):
    """Execute real graph routing with fixed LLM/provider doubles; return only safe outcomes."""
    fixture = WorkflowOfflineTests()
    fixture.setUp()
    from agents.outreach_followup_agent.workflow import OutreachFollowUpWorkflow
    from langgraph.checkpoint.memory import MemorySaver
    from sqlalchemy import select
    from database.models import OutreachRelationship
    repo = seed.repository
    w = OutreachFollowUpWorkflow(settings=fixture.settings, repository=repo,
        llm=fixture.workflow.llm, email_service=fixture.email,
        strategy_dispatcher=fixture.dispatcher, checkpointer=MemorySaver(),
        access_provider=lambda _: {"username": "evaluation_user", "password": "evaluation_password",
                                   "login_url": "https://rawaj.test"})
    ids = dict(restaurant_id=seed.restaurant_id, research_run_id=seed.research_run_id,
               qualification_run_id=seed.qualification_run_id)
    case = inputs["case"]
    result = w.start_outreach(**ids)
    if case == "reject":
        draft = result.email_draft
        result = w.resume_human_approval(thread_id=result.thread_id, reviewer_id="evaluation",
            decision="REJECTED", note="Make the opening more concise",
            message_id=draft.message_id, message_revision=draft.revision,
            content_sha256=w.graph.get_state(w._graph_config(result.thread_id)).values["approval_request"]["content_sha256"])
    elif case != "first_draft":
        draft = result.email_draft
        result = w.resume_human_approval(thread_id=result.thread_id, reviewer_id="evaluation",
            decision="APPROVED", message_id=draft.message_id, message_revision=draft.revision,
            content_sha256=w.graph.get_state(w._graph_config(result.thread_id)).values["approval_request"]["content_sha256"])
        if case in {"yes", "no", "strategy_ready"}:
            event = ButtonClickEvent(restaurant_id=1, outreach_message_id=result.email_draft.message_id,
                action=ButtonAction.NOT_INTERESTED if case == "no" else ButtonAction.INTERESTED,
                token_id="evaluation-verified-event")
            repo.record_button_event(event=event)
            result = w.resume_from_button_event(event)
            if case == "strategy_ready":
                result = w.receive_strategy_output(StrategyOutputHandoff(strategy_id=777,
                    restaurant_id=1, strategy_request_id=result.strategy_request.strategy_request_id,
                    status="READY", dashboard_strategy_url="https://dashboard.rawaj.test/strategy/777",
                    client_notification_allowed=True))
            elif case == "no":
                # Verify that a later scheduler tick cannot restart promotional contact.
                stopped = w.run_follow_up_due(**ids)
                if stopped.errors:
                    return {"error": "Follow-up after opt-out failed"}
        elif case in {"not_due", "follow_up_due"}:
            delta = -1 if case == "follow_up_due" else 60
            with seed.Session() as db:
                row = db.scalar(select(OutreachRelationship))
                row.next_contact_at = datetime.now(timezone.utc) + timedelta(minutes=delta)
                db.commit()
            result = w.run_follow_up_due(**ids)
    return {"action": result.decision.action.value if result.decision else None,
            "state": result.relationship_memory.status.value,
            "emails": len(fixture.email.sent), "strategy_requests": len(fixture.dispatcher.requests),
            "error": bool(result.errors)}

# Button handlers bypass the LLM decision node: action=None, with state and dispatch counts proving behavior.
# Expected outcomes are fixed references, never copied from actual results.
ACTION_CASES = [
    ("first_draft", "SEND_INITIAL_OUTREACH", "PENDING_OUTBOUND_APPROVAL", 0, 0),
    ("reject", "SEND_INITIAL_OUTREACH", "PENDING_OUTBOUND_APPROVAL", 0, 0),
    ("approve", "SEND_INITIAL_OUTREACH", "WAITING_FOR_RESPONSE", 1, 0),
    ("yes", None, "AWAITING_STRATEGY_OUTPUT", 1, 1),
    ("no", None, "DO_NOT_CONTACT", 1, 0),
    ("not_due", None, "WAITING_FOR_RESPONSE", 1, 0),
    ("follow_up_due", "SEND_FOLLOW_UP", "WAITING_FOR_RESPONSE", 2, 0),
    ("strategy_ready", "NOTIFY_STRATEGY_READY", "STRATEGY_DELIVERED", 2, 1),
]
ACTION_EXAMPLES = [{"inputs": {"case": c}, "outputs": dict(action=a, state=s, emails=n,
                    strategy_requests=r, error=False)} for c,a,s,n,r in ACTION_CASES]

def correct_action_state(outputs, reference_outputs):
    mismatches = [key for key, expected in reference_outputs.items() if outputs.get(key) != expected]
    return {"key": "correct_action_state", "score": int(not mismatches),
            "comment": "PASS" if not mismatches else "FAIL: " + ", ".join(mismatches)}

def content_example(name, observation):
    return {"inputs": {
        "research": {"restaurant": {"restaurant_id": 1, "name": name,
            "email": "evaluation@example.com", "location": "Jeddah"}, "research_run_id": 101,
            "analysis_status": "COMPLETED", "research_signals": [{"signal_id": "obs_1",
            "dimension": "content", "observation": observation}]},
        "qualification": {"restaurant_id": 1, "research_run_id": 101, "qualification_run_id": 202,
            "qualification": "Qualified for Rawaj.", "marketing_gaps": []}}, "outputs": {}}

# Synthetic fixtures are evidence for these evaluation cases, not claims about real businesses.
CONTENT_EXAMPLES = [
    content_example("Olive Table", "Recent Instagram posts receive little audience interaction."),
    content_example("Cedar Cafe", "Public posts feature seasonal iced drinks."),
    content_example("Harbor Kitchen", "No new Instagram posts were observed during the last 60 days."),
]

def email_target(inputs):
    """Use real decision/generation/review models in the existing graph; stop at human approval."""
    fixture = WorkflowOfflineTests()
    fixture.setUp()
    fixture.repository.load_research_handoff = lambda **kw: inputs["research"]
    fixture.repository.load_qualification_handoff = lambda **kw: inputs["qualification"]
    fixture.workflow.llm = RawajLLMService(get_settings())
    result = fixture.workflow.start_outreach(**IDS)
    if result.errors or result.email_draft is None:
        return {"error": "Agent failed to produce a reviewed draft", "subject": "", "body": ""}
    # Signed response URLs are trusted delivery details, not text to grade or upload.
    preview = fixture.workflow._redacted_draft_for_review(result.email_draft)
    return safe_preview({"error": None, "subject": preview["subject"], "body": preview["plain_text_body"]})
