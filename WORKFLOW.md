# Rawaj workflow

One pipeline, six stages. Stages 1-3 run in a single analysis job; 4-6 are triggered by the restaurant.

```
POST /api/restaurants/{id}/analyze                      (api/main.py → orchestration/workflow.py)
 │
 ├─ 1. Research         Instagram profile + content analysis          → research_runs
 ├─ 2. Qualification    marketing gaps + Qualified decision           → qualification_runs
 └─ 3. Outreach         email #1 drafted, then PAUSED                 → outbound_messages
                          │
                          ▼
          a second model reviews the email (language, grounding, privacy); if it passes,
          it is sent automatically (the `send_emails` node) — no staff step
                          ▼
   the restaurant clicks "Interested" in email #1              (outreach response service, server.py)
                          │  verified click → Strategy request written to strategy_handoffs/inbox/
                          ▼
 ├─ 4. Strategy         Strategy Agent, told the restaurant is Interested            → strategies
 │                        ReAct draft → self-reflection → guardrails → saved
 │                        (runs from the API every STRATEGY_POLL_SECONDS)
 └─ 5. Client email #2  "your strategy is ready" + username, password, dashboard link
                          reviewed and sent automatically, like email #1; it also tells the client
                          that Rawaj never asks for sensitive information by email or message
                          ▼
 6. The client signs in to the dashboard (username + password from email #2) and sees
    only their own restaurant: Home (gaps), Monthly Strategy (30-day plan), Content.

Background, while the API is up:  follow-ups for restaurants that did not answer
(FOLLOWUP_POLL_SECONDS) — reviewed and sent the same way.
```

The only human in the loop is the restaurant: it receives email #1 and decides by clicking "Interested".
An email is sent only if the review model marked it `passed` and `privacy_safe`, it is a routine type
(first email, follow-up, strategy-ready) and an email provider is configured. Anything else stays paused
(`/api/approvals` can list and decide those; there is no page for it). Set `AUTO_APPROVE_EMAILS=false` to
stop all automatic sending.

## Where things live

| Stage | Code |
|---|---|
| **The whole flow: one LangGraph** (research, qualification, outreach, strategy, notify client, send emails, follow-ups) | `orchestration/workflow.py` |
| Bridge from the graph into the Outreach Agent | `orchestration/outreach_node.py` |
| The agents themselves | `agents/research_agent/`, `agents/qualification_agent/`, `agents/outreach_followup_agent/`, `agents/strategy_agent/` |
| Manual decisions on emails that are never sent automatically | `api/approvals.py` (API only) |
| Client accounts and sign-in | `api/accounts.py`, `api/auth.py`, `user_accounts` table |
| Front-end | `rawaj_front/` (Streamlit) |

## Settings (.env)

| Variable | Needed for | Default |
|---|---|---|
| `OPENAI_API_KEY`, `TAVILY_API_KEY`, `APIFY_API_TOKEN` | research, qualification, strategy | — |
| `OPENAI_MODEL` | the one OpenAI model every agent uses (research, qualification, outreach, strategy, evals) | `gpt-5.6-luna` |
| `ACCOUNT_SECRET` (32+ random chars) | creating client accounts / email #2 | **required** |
| `DASHBOARD_URL` | the link in email #2 | `http://localhost:8501` |
| `BUTTON_SIGNING_SECRET` (32+ chars), `PUBLIC_BASE_URL` | the Interested / Not interested links in email #1 | — |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD` | staff sign-in to the front-end | disabled |
| `AUTO_APPROVE_EMAILS`, `AUTO_APPROVE_POLL_SECONDS` | send reviewed emails automatically | on, 30 s |
| `ADMIN_API_TOKEN` | protects the `/api/approvals` routes | open (local dev) |
| `EMAIL_PROVIDER` (`smtp`), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `FROM_EMAIL`, `FROM_NAME` | sending email (nothing is sent without them) | — |
| `RAWAJ_DEMO_LOGIN` | demo sign-in (any email + 6-char password) | `true` — set `false` for real use |
| `OUTREACH_AUTOSTART` | start Outreach right after Qualification | `true` |
| `PIPELINE_AUTORUN`, `STRATEGY_POLL_SECONDS`, `FOLLOWUP_POLL_SECONDS` | background stages | on, 30 s, 3600 s |

## Run

```
uvicorn api.main:app --reload                       # API + background stages (port 8000)
uvicorn agents.outreach_followup_agent.server:app   # email button links (needs PUBLIC_BASE_URL)
cd rawaj_front && streamlit run app.py              # dashboard (port 8501)
```

## Good to know

- Client passwords are derived from `ACCOUNT_SECRET` and the restaurant, so email #2 always carries the
  same credentials and only a hash is stored. Changing `ACCOUNT_SECRET` reissues every password.
- Email #2 contains the password in plain text (by design) and is sent without a person reading it. The
  password is hidden from the reviewing model.
- The API itself has no per-user login: the dashboard enforces sign-in, and only the `/api/approvals` routes
  have a token. Put the API behind your network or add API auth before exposing it publicly.
