
# Canonical Rawaj workflow

`schemas.py` owns Outreach relationship/action/message/handoff enums. Repository writes validate the relationship status. Research status, Qualification eligibility and email submission status are separate concepts.

| Event | State / effect |
|---|---|
| Qualified + grounded research | READY_TO_CONTACT → PENDING_OUTBOUND_APPROVAL |
| Reject with reason | New immutable replacement draft; review again |
| Human approve + provider acceptance | WAITING_FOR_RESPONSE; timer starts |
| Timeout within attempt limit | Reviewed automatic follow-up with response buttons |
| Confirm Yes | INTERESTED → AWAITING_STRATEGY_OUTPUT; timer cleared |
| Strategy complete | STRATEGY_READY → STRATEGY_DELIVERED after automatic notification |
| First owner login | ACTIVE_CLIENT; 30-day trial, feedback due day 27 |
| Feedback due | Automatic FEEDBACK_REQUEST; recorded once |
| Feedback submitted | client_feedback row + relationship memory |
| Confirm No | DO_NOT_CONTACT; timers cleared; outbound claims refused |

## Approval and recovery

Only INITIAL_OUTREACH interrupts for human approval. Approval binds ID, revision and hash. Rejection requires a reason and creates a replacement ID linked through supersedes_message_id. Later emails pass content/privacy review and receive an explicit system:outreach-policy authorization recorded as AUTOMATIC_AUTHORIZATION in the audit log. The shared authorization table remains for compatibility; system approval of initial outreach is refused.

send_reviewed_emails is a no-op compatibility entrypoint. AUTO_APPROVE_EMAILS cannot bypass the initial human gate. Internal escalations create review records without another approval interruption or customer email.

Signed buttons use GET to display confirmation and a one-time POST to apply the choice. Pending durable responses are recovered by the follow-up scheduler. Consent/provenance are checked before Strategy generation. The worker reuses an already saved strategy for its request and writes the notification outbox before moving the input to processed. Failed notification results remain queued.

Completed graph runs return their previous result on replay. Email claiming uses a conditional database update, including on SQLite. A crash after a provider may have accepted an email leaves SENDING for reconciliation; the system does not blindly resend it or claim exactly-once external delivery. SENT means provider acceptance, not proof the recipient read the message.

Tool services are scoped per graph invocation using ContextVar. Run one API process and one scheduler owner with SQLite. Multi-process/horizontal deployment requires distributed worker claims beyond this local setup.

## Integration

- main:app hosts data, approvals, login, trial, feedback and configured response routes.
- Strategy runs every 30 seconds by default; follow-ups every 15 seconds in demo and hourly in production.
- Set PIPELINE_AUTORUN=false before manual worker execution.
- `python -m agents.strategy_agent.strategy_worker --limit 10` runs Strategy and notification together.
- `python -m agents.outreach_followup_agent.follow_up_worker --kind prospect` runs due reminders.
- `python -m agents.outreach_followup_agent.follow_up_worker --kind client` runs due feedback requests.
- The standalone response server is optional when main:app already hosts PUBLIC_BASE_URL.

Keep database/checkpoints/secrets/outbox consistent. New lifecycle tables are additive. Owner login returns a short-lived signed token; trial/feedback endpoints derive the restaurant from that token. Feedback is stored for evaluation and improvement; it does not automatically retrain a model.

Qualification informs eligibility and internal selection. Customer generation receives vetted Research facts, optional real calendar context and rejection feedback; internal scores/gaps are not pasted into emails. Account details are appended by trusted code and removed before LLM review.
