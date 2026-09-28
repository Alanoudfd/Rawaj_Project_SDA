# Rawaj_Project_SDA

Rawaj is a multi-agent marketing system for restaurants. It finds and researches restaurant prospects, qualifies them, contacts them by email, and gives interested restaurants a personalised marketing strategy during a 30-day trial.

The project has two web interfaces. Both use the same FastAPI backend and database:

| Interface | Who uses it | Default URL |
| --- | --- | --- |
| **Agency workspace** (`agency/`) | The Rawaj team: prospects, outreach approval, strategies, feedback | http://127.0.0.1:8010/agency |
| **Restaurant dashboard** (`rawaj_front/`, Streamlit) | Restaurant owners: marketing gaps, strategy, content plan | http://127.0.0.1:8502 |

## How it works

```
Research ─► Qualification ─► Outreach (human approves first email) ─► Response
                                                                        │
                    Interested ◄────────────────────────────────────────┤
                        │                                  Not interested ─► stop
                        ▼
               Strategy generated ─► onboarding email + login ─► 30-day trial ─► feedback
```

| Agent | Folder | Role |
| --- | --- | --- |
| Research | `agents/research_agent/` | Scrapes and analyses the restaurant's online presence (Apify, Tavily) |
| Qualification | `agents/qualification_agent/` | Decides whether the prospect is a good fit and finds marketing gaps |
| Outreach & Follow-up | `agents/outreach_followup_agent/` | Drafts emails, sends them after approval, sends reminders, handles responses |
| Strategy | `agents/strategy_agent/` | Builds the marketing strategy, content ideas and post kits |

LangGraph ties the agents together in `orchestration/`. The API lives in `api/` and the database layer (SQLAlchemy) in `database/`. For the full state machine, see [WORKFLOW.md](WORKFLOW.md).

## Requirements

- **Python 3.11**
- An internet connection and a web browser
- API keys for:
  - **OpenAI** (required), with a model your account can use
  - **Apify** and **Tavily** (required for research)
  - **Resend** *or* an **SMTP** server (required to send emails)
  - LangSmith and Google Calendar (optional)

You don't need Node.js or npm. The Agency frontend is plain HTML/JS served by the backend.

## 1. Install

From the project root (the folder containing `requirements.txt`):

**Windows (PowerShell)**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

**macOS / Linux**

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

`requirements.txt` also installs the Streamlit restaurant dashboard, so you don't need a separate install for it.

> Copy `.env.example` only the first time. Don't overwrite a `.env` that already works.

## 2. Configure `.env`

Open `.env` and fill in your own values. **Never commit this file.**

### Required settings

```dotenv
RAWAJ_ENV=demo
DATABASE_URL=sqlite:///rawaj.db

OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=a-model-your-account-can-use

APIFY_API_TOKEN=your-apify-token
TAVILY_API_KEY=your-tavily-key

BUTTON_SIGNING_SECRET=first-random-secret
ACCOUNT_SECRET=second-random-secret
```

Leave `OPENAI_GENERATION_MODEL`, `OPENAI_DECISION_MODEL` and `OPENAI_REVIEW_MODEL` empty to use `OPENAI_MODEL` for everything.

### Generate the two secrets

Run this command twice to get two different values:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

`ACCOUNT_SECRET` must be at least 32 characters. **Keep both secrets the same once you've set them.** If you change them, existing restaurant logins and email buttons stop working.

### Email provider (choose one)

**Resend**

```dotenv
EMAIL_PROVIDER=resend
RESEND_API_KEY=your-resend-key
FROM_EMAIL=sender-address-verified-with-resend
FROM_NAME=Rawaj Team
```

**SMTP**

```dotenv
EMAIL_PROVIDER=smtp
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-username
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
FROM_EMAIL=your-sender-address
FROM_NAME=Rawaj Team
```

### Other settings

The defaults in `.env.example` work for local use:

| Variable | Default | Meaning |
| --- | --- | --- |
| `PIPELINE_AUTORUN` | `true` | Run Strategy and follow-ups automatically in the background |
| `STRATEGY_POLL_SECONDS` | `30` | How often to check for pending strategy requests |
| `FOLLOW_UP_MAX_ATTEMPTS` | `3` | Initial email plus up to 2 reminders |
| `FOLLOW_UP_DELAY_MINUTES` | demo: `2`, production: `10080` (7 days) | Wait time before a reminder |
| `FOLLOWUP_POLL_SECONDS` | demo: `15`, production: `3600` | How often to check for due reminders |
| `LANGSMITH_TRACING` | `false` | Set to `true` (plus LangSmith keys) to trace runs |
| `RAWAJ_EVENTS_CALENDAR_ID`, `GOOGLE_SERVICE_ACCOUNT_FILE` | empty | Optional Google Calendar enrichment |

## 3. Run

One command starts the backend, the Agency workspace and the restaurant dashboard:

**Windows**

```powershell
.\.venv\Scripts\python.exe -m scripts.agency_workspace
```

**macOS / Linux**

```bash
.venv/bin/python -m scripts.agency_workspace
```

Then open:

- Agency workspace: http://127.0.0.1:8010/agency
- Restaurant dashboard: http://127.0.0.1:8502

The backend creates the database tables automatically on first start, so a fresh install begins empty. Keep the terminal open while you work and press **Ctrl+C** to stop. When you restart with the same `.env` and database, your progress is still there.

**Launcher options**

```powershell
# Use different ports if 8010 / 8502 are busy
.\.venv\Scripts\python.exe -m scripts.agency_workspace --port 8011 --client-port 8503

# Browse the UI without background Strategy generation or automatic follow-ups
.\.venv\Scripts\python.exe -m scripts.agency_workspace --pause-automation
```

### Running the parts separately (optional)

```powershell
# Backend API only
python -m uvicorn main:app --reload --port 8010

# Restaurant dashboard only (set RAWAJ_API_URL to the backend URL)
cd rawaj_front
streamlit run app.py
```

If you want to run the background workers by hand, set `PIPELINE_AUTORUN=false` first:

```powershell
python -m agents.strategy_agent.strategy_worker --limit 10
python -m agents.outreach_followup_agent.follow_up_worker --kind prospect   # reminders
python -m agents.outreach_followup_agent.follow_up_worker --kind client     # feedback requests
```

## 4. Using the Agency workspace

1. **Prospects**: add a restaurant, or select an existing one. Reuse existing research instead of creating duplicates.
2. Run **Research** and **Qualification**, then check the saved results.
3. **Outreach**: generate the first email draft and review the recipient, subject and body.
   - To change the draft, reject it with a reason and a new draft is generated.
   - **Approve** sends a real email to the recipient shown.
4. The restaurant replies with the buttons in the email:
   - **Interested**: Rawaj generates a strategy, then automatically sends a second email with the dashboard link and login details.
   - **Not interested**: Rawaj stops all further emails.
   - **No reply**: Rawaj sends reminders automatically, based on the delay and attempt limit.
5. The 30-day trial starts when the restaurant first logs in. Rawaj requests feedback near the end of the trial and shows it on the **Feedback** page.

Emailed links point to `127.0.0.1`, so they only work on the computer running Rawaj. To share a demo online, deploy the backend and dashboard on public HTTPS URLs and update `PUBLIC_BASE_URL`, `DASHBOARD_URL` and `RAWAJ_API_URL`. The Agency workspace has no login, so never expose it publicly without network-level protection.

## 5. Tests and evaluation

```powershell
# Unit and integration tests (no real emails or live model calls)
python -m pytest tests -q

# Agent evaluations (use OpenAI and LangSmith)
python -m evals.run_all                      # all agents
python -m evals.run_all --agents research --limit 5 --no-judges
```

The Jupyter notebooks for evaluation are in each agent's `evaluation/` folder. Running them requires `pip install jupyterlab ipykernel`. Don't run notebook workers while the launcher is running against the same database.

## Project structure

```
agency/           Agency workspace frontend + its API routes
agents/           Research, Qualification, Outreach/Follow-up and Strategy agents
api/              FastAPI app (api/main.py) and endpoints
database/         SQLAlchemy models and repositories
orchestration/    LangGraph workflow connecting the agents
rawaj_front/      Streamlit restaurant dashboard
scripts/          Launcher and helper scripts
evals/            Agent evaluation suite (LangSmith)
tests/            Pytest test suite
main.py           Entry point: exposes the FastAPI app
```

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Prospects list is empty | A fresh install has no data. Add a prospect and run research. |
| No draft is generated | Research and qualification are saved; OpenAI key, model access and quota are valid; restart after editing `.env`. |
| Stuck on "Awaiting Strategy Output" | Automation is running (no `--pause-automation`) and only one launcher is running. |
| Email link doesn't open | The server is running, and you're opening the link on the same computer. |
| Restaurant login fails | Use the credentials from this installation's onboarding email, and make sure `ACCOUNT_SECRET` hasn't changed. |
| "Database is locked" | Only one launcher or worker should be using the database at a time. |

For more detail, see [Guide Starting from Rawaj Agency User Interface.md](Guide%20Starting%20from%20Rawaj%20Agency%20User%20Interface.md), [agency/README.md](agency/README.md) and [rawaj_front/README.md](rawaj_front/README.md).

## Don't commit

`.env`, `rawaj.db` (and other database files or backups), `rawaj_outreach_checkpoints*`, `strategy_handoffs/`, `.venv/`, and any credential or service-account files.
