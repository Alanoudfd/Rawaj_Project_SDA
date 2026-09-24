# Guide Starting from Rawaj Agency User Interface

## 1. Architecture and prerequisites

The Agency workspace and restaurant interface are separate applications connected to the same Rawaj backend and database. Agency manages prospects, outreach approval, strategies, trials and feedback. Restaurant access uses the restaurant's provisioned account. Agency has no login in this version.

Install Python 3.11 and use an internet connection and a browser. Git is optional unless cloning/publishing. Supply your own OpenAI API key and accessible model, Apify token, Tavily key where research requires it, and Resend or SMTP credentials. LangSmith and Google Calendar are optional. The Agency frontend needs no npm build.

The GitHub-ready package contains source, not the author's private database or credentials. A fresh installation starts empty and creates its schema during backend startup. Teammates should add their own prospects rather than copy experiment databases.

## 2. Install

Open the project root containing requirements.txt, agency, api and agents.

Windows PowerShell:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

macOS/Linux:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Copy the example only on first setup; never overwrite a working .env. requirements.txt includes the restaurant frontend dependencies. requirements-tested.txt is a historical backend dependency snapshot, not the complete interface installation command.

## 3. Configure .env

Edit .env locally and never commit it. Replace placeholders with your own settings:

```dotenv
RAWAJ_ENV=demo
DATABASE_URL=sqlite:///rawaj.db
LANGGRAPH_CHECKPOINT_PATH=rawaj_outreach_checkpoints.sqlite
STRATEGY_HANDOFF_OUTBOX=strategy_handoffs/inbox
OPENAI_API_KEY=YOUR_OWN_KEY
OPENAI_MODEL=YOUR_ACCESSIBLE_MODEL
APIFY_API_TOKEN=YOUR_OWN_TOKEN
TAVILY_API_KEY=YOUR_OWN_KEY
BUTTON_SIGNING_SECRET=YOUR_FIRST_RANDOM_SECRET
ACCOUNT_SECRET=YOUR_SECOND_RANDOM_SECRET
PUBLIC_BASE_URL=http://127.0.0.1:8010
DASHBOARD_URL=http://127.0.0.1:8502
RAWAJ_API_URL=http://127.0.0.1:8010
ALLOW_LOCAL_BUTTON_DEMO=true
RAWAJ_DEMO_LOGIN=false
PIPELINE_AUTORUN=true
STRATEGY_POLL_SECONDS=30
FOLLOW_UP_MAX_ATTEMPTS=3
LANGSMITH_TRACING=false
```

Leave OPENAI_GENERATION_MODEL, OPENAI_DECISION_MODEL and OPENAI_REVIEW_MODEL blank to use the shared model setting, or supply explicit accessible models. Other agents may have their own model configuration; investigate the relevant agent if it reports an unavailable model.

Generate a random secret with this command, run twice for two different values:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

ACCOUNT_SECRET must be at least 32 characters. Keep both secrets stable across restarts. Existing restaurant credentials depend on the original account secret; existing email buttons depend on their signing secret. Never regenerate them simply to reopen the application.

Choose one real email provider. For Resend:

```dotenv
EMAIL_PROVIDER=resend
RESEND_API_KEY=YOUR_OWN_KEY
FROM_EMAIL=YOUR_AUTHORIZED_SENDER
FROM_NAME=Rawaj Team
```

For SMTP instead:

```dotenv
EMAIL_PROVIDER=smtp
SMTP_HOST=YOUR_HOST
SMTP_PORT=587
SMTP_USERNAME=YOUR_USERNAME
SMTP_PASSWORD=YOUR_PASSWORD
SMTP_USE_TLS=true
FROM_EMAIL=YOUR_AUTHORIZED_SENDER
FROM_NAME=Rawaj Team
```

Use sender and recipient addresses permitted by your provider account. Provider acceptance does not guarantee inbox delivery; inspect spam and provider records when necessary.

## 4. Start both interfaces with automation enabled

Windows:

```powershell
.\.venv\Scripts\python.exe -m scripts.agency_workspace
```

macOS/Linux:

```bash
.venv/bin/python -m scripts.agency_workspace
```

- Agency: http://127.0.0.1:8010/agency
- Restaurant: http://127.0.0.1:8502

Keep the terminal running. The launcher starts the backend and restaurant interface, sets matching local URLs and enables automatic processing. Do not add --pause-automation for the full workflow. Do not run another notebook/server/background worker against the same database concurrently.

Stop deliberately using Ctrl+C. Restart with the same database and .env to preserve progress. If this workspace already occupies the ports, use its existing links. Otherwise choose unused ports:

```powershell
.\.venv\Scripts\python.exe -m scripts.agency_workspace --port 8011 --client-port 8503
```

New emails use the new ports; previously sent links do not update automatically.

## 5. Agency workflow

1. Add a prospect or select an existing record. Reuse existing research rather than create duplicates.
2. Complete Research and Qualification and check the saved results.
3. Open Outreach and generate the initial draft. Review recipient, subject and body.
4. For revision, supply a rejection/regeneration reason and review the new draft.
5. Approve the correct draft. This authorizes a real email to the displayed recipient.
6. Follow the saved delivery and response statuses. A draft alone is not a sent email.

Dashboard provides summaries and action links. Prospects contains restaurant details and lifecycle summaries. Outreach is the primary home for email actions; Feedback is the primary home for client feedback.

After an Interested response, Strategy generates and saves its output and signals Outreach. The second email is sent automatically with the dashboard link and provisioned credentials, without human approval. The polling interval is not a completion deadline: model calls and strategy processing take additional time.

A Not Interested response stops follow-up. With no response, automatic reminders follow the configured delay and attempt limit. The 30-day trial starts on activation, not the initial email date. Demonstrating restaurant activation can therefore start its trial. Feedback near the trial end is saved against the relationship.

## 6. Timing and local access

Without timing overrides, demo follow-up delay is two minutes and production delay is seven days. FOLLOW_UP_MAX_ATTEMPTS=3 includes the initial email and up to two reminders. Optional demo overrides are:

```dotenv
FOLLOW_UP_DELAY_MINUTES=2
FOLLOWUP_POLL_SECONDS=15
```

Remove these overrides or change them appropriately when moving to production; seven days is 10080 minutes. Background processing requires the backend to remain running.

The agency_workspace launcher is for local demonstrations and deliberately supplies local URLs. localhost/127.0.0.1 refers to the computer opening the link. Open local email buttons and dashboard links on the computer running Rawaj. A phone or another teammate's computer cannot use those links to reach your computer.

Each teammate can run a fresh checkout with their own .env and database. For a shared online presentation, deploy reachable backend/client URLs with HTTPS separately. Protect the Agency route at the deployment/network layer: a separate route is not authentication.

## 7. Optional notebooks, tracing and calendar

Agency does not require notebooks. To open the existing notebooks in the same environment:

```powershell
.\.venv\Scripts\python.exe -m pip install jupyterlab ipykernel
.\.venv\Scripts\python.exe -m jupyter lab
```

Select this environment's kernel. Outreach evaluation lives in agents/outreach_followup_agent/evaluation/outreach_agent_evaluation.ipynb and covers action/state correctness plus personalization/groundedness. Follow its setup cells for LangSmith tracing. Keep passwords and service credentials out of traces.

Do not start duplicate live workers from notebook cells alongside Agency. Older notebooks may reference generated research inputs or experiment databases excluded from this source package; regenerate or provide your own local inputs.

Calendar enrichment is optional. Configure RAWAJ_EVENTS_CALENDAR_ID and GOOGLE_SERVICE_ACCOUNT_FILE when needed, grant calendar access to the service account, and keep its credentials private. Install Google client dependencies required by the selected calendar integration. Calendar configuration is not necessary for the standard Agency flow.

## 8. Troubleshooting

| Symptom | Check |
| --- | --- |
| Empty prospects | Fresh checkout has no private records; add/select a prospect and run research. |
| No draft | Saved Research/Qualification, relationship status, model access, quota, network and backend error. Restart after configuration changes. |
| Awaiting Strategy Output | Keep automation running and inspect Strategy request/errors and provider settings. Avoid duplicate workers. |
| Strategy ready, second email missing | Saved delivery status, email settings and stable ACCOUNT_SECRET. Do not send another initial email to repair onboarding. |
| Link fails | Running server, matching host/ports, and opening local links on the server computer. |
| Restaurant login fails | Credentials from this installation's onboarding email, matching database and original ACCOUNT_SECRET. |
| Stale approval | Refresh Outreach and review the latest saved draft. |
| Missing saved data | DATABASE_URL; notebook experiment databases are not automatically merged into rawaj.db. |
| Database locked | Keep one workspace launcher and stop unintended duplicate processes. |

Do not repair credentials by blindly deleting the database or rotating ACCOUNT_SECRET. Preserve matching configuration and data together.

## 9. GitHub exclusions and experiment cleanup

Include source code, both interface directories, agents, API, model/schema code, orchestration, scripts, requirements, .env.example, documentation, tests and evaluation source/datasets. Preserve teammates' source files.

Exclude these local artifacts from upload:

| Item | Reason |
| --- | --- |
| .env and private environment files | API keys and stable secrets |
| rawaj.db, other database files and sidecars | Private records, accounts and experiment state |
| rawaj_outreach_checkpoints* | Local workflow checkpoints |
| strategy_handoffs/ | Local handoff queue/state |
| .venv/, venv/, env/, node_modules/ | Machine-specific dependencies |
| work/, .runtime/, caches, logs, outputs/ | Local generated artifacts |
| research_results/, results/, *_qualification_input.json | Saved experiment inputs/results |
| agents/qualification_agent/evaluation_results.json | Generated evaluation output |
| secrets/, credentials/, service-account/token files | Integration credentials |
| Notebook outputs and widget state | May contain emails, credentials or previous results |

The GitHub-ready ZIP excludes these artifacts and clears notebook outputs in packaged copies only. Original working notebooks and runtime state are preserved. Legacy scripts referencing excluded inputs need their own new local inputs.

Do not delete the current rawaj.db, .env, checkpoints or handoffs just to upload code. Excluding them is enough. No reset is needed for teammates using fresh checkouts. For a deliberate future reset, stop the application and back up the database, matching secrets and workflow state together first.

.gitignore does not untrack previously committed files. Remove specific private files from Git's index while retaining local copies if necessary, then inspect staged changes. If a real key was previously published, revoke it with the provider and address repository history; ignoring it does not erase old commits.

## 10.  checklist

- Install Python and requirements in a virtual environment.
- Create a private .env with working service credentials.
- Generate the two stable secrets once and retain them.
- Launch scripts.agency_workspace without pausing automation.
- Open Agency, add/select a prospect and complete Research/Qualification.
- Review the first draft before authorizing real delivery.
- Use the server computer for local email links and restaurant access.
- Keep one launcher running and preserve its database/configuration across restarts.
