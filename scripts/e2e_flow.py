"""End-to-end test of the whole Rawaj flow, from analysis to the client signing in.

    python scripts/e2e_flow.py                # the full run (about 5-8 minutes, uses OpenAI and Tavily)
    python scripts/e2e_flow.py --setup-only   # only checks the setup (free, a few seconds)
    python scripts/e2e_flow.py --new-name "Cafe X" --new-instagram cafe.x --new-location Jeddah
                                              # a brand-new restaurant: research + qualification run from scratch

What it does, in order (each step prints PASS or FAIL):
  1. analyze      research -> qualification (reused from the database) -> outreach drafts email 1
  2. send emails  a second model reviewed email 1; it is sent automatically
  3. the restaurant clicks "Interested" in email 1 (the real confirmation page, GET then POST)
  4. strategy     the Strategy Agent writes the 30-day plan, knowing the restaurant is interested
  5. send emails  email 2 (username, password, dashboard link, privacy note) is reviewed and sent
  6. sign in      the client logs in with the credentials from email 2 and sees the strategy
  7. not interested   a second restaurant clicks "No, thank you": contact stops for good
  8. no response     a third restaurant does not answer: after the waiting time a follow-up is sent

It is safe to run:
  - it works on a COPY of rawaj.db in a temporary folder; your database is not touched;
  - emails go to a small mail server inside this script, so nothing is sent to anyone;
  - LangSmith tracing is switched off for the run, so the test password is not traced.

The result is the last line: "N/N checks passed". Any FAIL line says what broke.
Needs OPENAI_API_KEY and TAVILY_API_KEY in .env, and one restaurant with saved research and qualification.
"""

import argparse
import html as htmllib
import os
import re
import secrets
import shutil
import socket
import socketserver
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
from email import message_from_bytes, policy
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = Path(tempfile.mkdtemp(prefix="rawaj-e2e-"))
TEST_EMAIL = "owner@rawaj-test.example"


def free_port():
    """A port nothing is using, so two runs (or a running API) never collide."""
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


SMTP_PORT, RESPONSE_PORT = free_port(), free_port()

parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("--setup-only", action="store_true", help="check the setup and stop before any paid call")
parser.add_argument("--new-name", help="test a brand-new restaurant (added to the temporary copy of the database only)")
parser.add_argument("--new-instagram", help="the new restaurant's Instagram username, without @")
parser.add_argument("--new-location", help="the new restaurant's location, e.g. Jeddah")
ARGS = parser.parse_args()
if bool(ARGS.new_name) != bool(ARGS.new_instagram):
    parser.error("--new-name and --new-instagram must be given together")

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

shutil.copy(ROOT / "rawaj.db", RUN_DIR / "e2e.db")
os.environ.update(
    DATABASE_URL="sqlite:///" + (RUN_DIR / "e2e.db").as_posix(),
    LANGGRAPH_CHECKPOINT_PATH=str(RUN_DIR / "checkpoints.sqlite"),
    STRATEGY_HANDOFF_OUTBOX=str(RUN_DIR / "strategy_handoffs" / "inbox"),
    EMAIL_PROVIDER="smtp", SMTP_HOST="127.0.0.1", SMTP_PORT=str(SMTP_PORT), SMTP_USERNAME="test", SMTP_PASSWORD="test",
    SMTP_USE_TLS="false", FROM_EMAIL="hello@rawaj.test", FROM_NAME="Rawaj",
    BUTTON_SIGNING_SECRET=secrets.token_urlsafe(48), PUBLIC_BASE_URL=f"http://127.0.0.1:{RESPONSE_PORT}",
    ALLOW_LOCAL_BUTTON_DEMO="true", ACCOUNT_SECRET=secrets.token_urlsafe(48), DASHBOARD_URL="http://localhost:8501",
    AUTO_APPROVE_EMAILS="true",
)

results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""), flush=True)
    return ok


def banner(text):
    print(f"\n=== {text} ===", flush=True)


def create_new_restaurant():
    """Add the restaurant given on the command line to the temporary copy of the database."""
    username = ARGS.new_instagram.strip().lstrip("@").lower()
    with sqlite3.connect(RUN_DIR / "e2e.db") as db:
        if db.execute("select 1 from restaurants where lower(instagram_username) = ?", (username,)).fetchone():
            raise SystemExit(f"A restaurant with the Instagram username {username} already exists in the database.")
    from database.database import Base, engine, ensure_legacy_database_schema
    from database.models import Restaurant

    Base.metadata.create_all(engine)
    ensure_legacy_database_schema(engine)
    from sqlalchemy.orm import Session

    with Session(engine) as session:
        restaurant = Restaurant(
            name=ARGS.new_name, instagram_username=username,
            instagram_url=f"https://www.instagram.com/{username}/", email=TEST_EMAIL, location=ARGS.new_location,
        )
        session.add(restaurant)
        session.commit()
        return restaurant.id, restaurant.name


def pick_restaurant():
    """A restaurant whose saved research matches the default settings, so nothing is scraped again."""
    if ARGS.new_name:
        return create_new_restaurant()
    with sqlite3.connect(RUN_DIR / "e2e.db") as db:
        row = db.execute(
            """select r.id, r.name from restaurants r
               join research_runs rr on rr.restaurant_id = r.id
               join qualification_runs q on q.research_run_id = rr.id
               where rr.status = 'complete' and rr.content_limit = 30 and rr.lookback_days = 90 and q.status = 'completed'
               order by r.id limit 1"""
        ).fetchone()
    if row is None:
        raise SystemExit("No restaurant has saved research (30 items, 90 days) and a qualification. Run an analysis first.")
    return row


# ------------------------------------------------------------------ a tiny mail server that keeps the emails
INBOX = []


class SmtpHandler(socketserver.StreamRequestHandler):
    def reply(self, text):
        self.wfile.write((text + "\r\n").encode())

    def handle(self):
        self.reply("220 localhost test sink")
        recipients = []
        while True:
            line = self.rfile.readline()
            if not line:
                return
            command = line.decode("utf-8", "replace").rstrip("\r\n")
            upper = command.upper()
            if upper.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-localhost\r\n250-AUTH PLAIN LOGIN\r\n250 8BITMIME\r\n")
            elif upper.startswith("AUTH PLAIN"):
                self.reply("235 2.7.0 accepted")
            elif upper.startswith("AUTH LOGIN"):
                self.reply("334 VXNlcm5hbWU6"); self.rfile.readline()
                self.reply("334 UGFzc3dvcmQ6"); self.rfile.readline()
                self.reply("235 2.7.0 accepted")
            elif upper.startswith("MAIL FROM"):
                recipients = []; self.reply("250 ok")
            elif upper.startswith("RCPT TO"):
                recipients.append(re.search(r"<([^>]*)>", command).group(1)); self.reply("250 ok")
            elif upper == "DATA":
                self.reply("354 end with <CRLF>.<CRLF>")
                data = b""
                while True:
                    chunk = self.rfile.readline()
                    if chunk in (b".\r\n", b""):
                        break
                    data += chunk[1:] if chunk.startswith(b"..") else chunk
                INBOX.append((recipients, message_from_bytes(data, policy=policy.default)))
                self.reply("250 queued")
            elif upper in ("RSET", "NOOP"):
                self.reply("250 ok")
            elif upper == "QUIT":
                self.reply("221 bye"); return
            else:
                self.reply("502 not implemented")


class Sink(socketserver.ThreadingTCPServer):
    allow_reuse_address = False
    daemon_threads = True


def plain_text(message):
    part = message.get_body(preferencelist=("plain",))
    return part.get_content() if part else ""


RESTAURANT_ID, RESTAURANT_NAME = pick_restaurant()
print(f"Run folder: {RUN_DIR}\nRestaurant: {RESTAURANT_NAME} (id {RESTAURANT_ID}); emails go to {TEST_EMAIL} on the local mail server only.", flush=True)

sink = Sink(("127.0.0.1", SMTP_PORT), SmtpHandler)
threading.Thread(target=sink.serve_forever, daemon=True).start()

import requests

response_server = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "agents.outreach_followup_agent.server:app", "--port", str(RESPONSE_PORT), "--log-level", "warning"],
    cwd=ROOT, env=os.environ.copy(), stdout=open(RUN_DIR / "response_server.log", "w"), stderr=subprocess.STDOUT,
)
try:
    for _ in range(60):
        try:
            if requests.get(f"http://127.0.0.1:{RESPONSE_PORT}/health", timeout=2).ok:
                break
        except requests.RequestException:
            time.sleep(1)

    from sqlalchemy import text

    from database.database import Base, engine, ensure_legacy_database_schema

    Base.metadata.create_all(engine)
    ensure_legacy_database_schema(engine)  # adds columns that newer code expects to an older database copy
    with engine.begin() as connection:
        connection.execute(text("update restaurants set email = :e where id = :i"), {"e": TEST_EMAIL, "i": RESTAURANT_ID})

    from agents.outreach_followup_agent.agent import RawajOutreachApplication
    from api import accounts
    from orchestration import workflow

    application = RawajOutreachApplication.create(access_provider=accounts.provision_access)
    factory = lambda: application

    banner("Setup")
    check("the response service (email button page) is up", requests.get(f"http://127.0.0.1:{RESPONSE_PORT}/health", timeout=5).ok)
    check("the email settings point to the local mail server", application.settings.email_provider == "smtp")
    if ARGS.setup_only:
        raise SystemExit(0)

    # ---------------------------------------------------------------- 1. analyze -> outreach (email 1 drafted)
    banner("1. analyze: research -> qualification -> outreach (graph event 'analyze')")
    outreach = {}
    for attempt in range(1, 4):  # the review model is strict; a draft it rejects is simply generated again
        result = workflow.run_restaurant_workflow(RESTAURANT_ID, start_outreach=True)
        outreach = result.get("outreach", {})
        print(f"attempt {attempt}: error={result.get('error')} | qualification_run={result.get('qualification_run_id')} | outreach={outreach.get('status')} errors={outreach.get('errors')}", flush=True)
        if outreach.get("pending_human_approval"):
            break
    check("analysis reused the stored research and qualification", result.get("qualification_run_id") and not result.get("error"))
    check("email 1 drafted and reviewed (paused before sending)", outreach.get("pending_human_approval"), f"status={outreach.get('status')}")

    # ---------------------------------------------------------------- 2. send email 1
    banner("2. send_emails: the reviewed email is sent automatically")
    summary = workflow.send_reviewed_emails(factory)
    print(summary, flush=True)
    check("email 1 approved automatically", len(summary.get("approved", [])) == 1 and not summary["approved"][0]["errors"])
    check("email 1 reached the mail server", len(INBOX) == 1 and INBOX[0][0] == [TEST_EMAIL], f"{len(INBOX)} message(s)")
    if not INBOX:
        raise SystemExit(1)
    email1 = plain_text(INBOX[0][1])
    print("subject:", INBOX[0][1]["Subject"], flush=True)
    interested = re.search(r"interested:\s*(https?://\S+)", email1, re.I)
    check("email 1 has the Interested link", interested)

    # ---------------------------------------------------------------- 3. the restaurant clicks Interested
    banner("3. the restaurant clicks Interested (GET shows the page, POST confirms)")
    page = requests.get(interested.group(1), timeout=20)
    check("GET shows the confirmation page without changing anything", page.ok and "confirm" in page.text.lower())
    form = {name: htmllib.unescape(value) for name, value in re.findall(r'name="(token|confirmation)" value="([^"]*)"', page.text)}
    action = urljoin(interested.group(1), htmllib.unescape(re.search(r'<form method="post" action="([^"]*)"', page.text).group(1)))
    confirmed = requests.post(action, data=form, timeout=90)
    print("POST ->", confirmed.status_code, re.sub(r"<[^>]+>", " ", confirmed.text).split()[:12], flush=True)
    check("POST confirmed the response", confirmed.ok)
    inbox_dir = RUN_DIR / "strategy_handoffs" / "inbox"
    written = [f.name for f in inbox_dir.glob("*.json")] if inbox_dir.is_dir() else []
    check("a Strategy request was written to the inbox", len(written) == 1, str(written))

    # ---------------------------------------------------------------- 4. strategy + email 2
    banner("4. strategy_inbox: Strategy Agent (knows the restaurant is interested) -> email 2")
    stage = workflow.run_strategy_stage(application_factory=factory)
    saved = [i for i in stage.get("items", []) if i.get("status") == "STRATEGY_GENERATED_AND_SAVED"]
    check("strategy generated (draft + Shaimaa's self-reflection) and saved", len(saved) == 1, str(stage.get("items")))
    notifications = stage.get("notifications", [])
    check("email 2 drafted for the client", notifications and isinstance(notifications[0]["notification"], dict), str(notifications)[:200])

    banner("5. send_emails: email 2 is sent automatically")
    summary2 = workflow.send_reviewed_emails(factory)
    print(summary2, flush=True)
    check("email 2 approved automatically", len(summary2.get("approved", [])) == 1 and not summary2["approved"][0]["errors"])
    check("email 2 reached the mail server", len(INBOX) == 2, f"{len(INBOX)} message(s)")
    email2 = plain_text(INBOX[1][1]) if len(INBOX) > 1 else ""
    print("subject:", INBOX[1][1]["Subject"] if len(INBOX) > 1 else None, flush=True)
    print("----- email 2 -----\n" + email2 + "\n----- end -----", flush=True)
    username = (re.search(r"Username:\s*(\S+)", email2) or [None, None])[1]
    password = (re.search(r"Password:\s*(\S+)", email2) or [None, None])[1]
    check("email 2 has username, password and the sign-in link", username and password and "Sign in here: http://localhost:8501" in email2)
    check("email 2 has the strategy link", "http://localhost:8501/strategy" in email2)
    check("email 2 tells the client we never collect sensitive information", "never asks you to send passwords" in email2)

    # ---------------------------------------------------------------- 6. the client signs in
    banner("6. the client signs in with the credentials from email 2")
    from fastapi.testclient import TestClient

    from api.main import create_app

    with TestClient(create_app(database_engine=engine)) as client:
        login = client.post("/api/auth/login", json={"username": username or "x", "password": password or "x"})
        print("login ->", login.status_code, login.json(), flush=True)
        check("login works and lands on the client's own restaurant", login.status_code == 200 and login.json().get("restaurant_id") == RESTAURANT_ID)
        check("a wrong password is refused", client.post("/api/auth/login", json={"username": username or "x", "password": "wrong"}).status_code == 401)
        strategy = client.get(f"/api/restaurants/{RESTAURANT_ID}/agent-strategy")
        body = strategy.json() if strategy.status_code == 200 else {}
        print("strategy ->", strategy.status_code, {k: body.get(k) for k in ("id", "start_date", "end_date", "interest_event_id")}, "days:", len(body.get("days", [])), flush=True)
        check("the dashboard shows a 30-day strategy tied to the Interested click", len(body.get("days", [])) == 30 and body.get("interest_event_id"))
    # ---------------------------------------------------------------- 7-8. the two other endings
    from agents.outreach_followup_agent.agent import run_outreach_after_qualification

    with sqlite3.connect(RUN_DIR / "e2e.db") as raw:
        others = raw.execute(
            """select r.id, r.name, rr.id, q.id from restaurants r
               join research_runs rr on rr.restaurant_id = r.id
               join qualification_runs q on q.research_run_id = rr.id
               where r.id != ? and rr.status = 'complete' and q.status = 'completed'
               group by r.id order by r.id""",
            (RESTAURANT_ID,),
        ).fetchall()

    def db(sql, *params):
        with sqlite3.connect(RUN_DIR / "e2e.db") as raw:
            rows = raw.execute(sql, params).fetchall()
            raw.commit()
            return rows

    def start_and_send(restaurant_id, research_id, qualification_id, address):
        """Email 1 for another restaurant: written (again if the review rejects it), then sent."""
        db("update restaurants set email = ? where id = ?", address, restaurant_id)
        outcome = workflow._write_until_reviewed(lambda: run_outreach_after_qualification(
            restaurant_id=restaurant_id, research_run_id=research_id, qualification_run_id=qualification_id, application=application,
        ))
        workflow.send_reviewed_emails(factory)
        return outcome

    def a_week_passes(restaurant_id):
        """Move the first email 8 days into the past, as if a week went by without an answer."""
        db("update outbound_messages set sent_at = datetime('now', '-8 days'), created_at = datetime('now', '-8 days') where restaurant_id = ?", restaurant_id)
        db("update outreach_relationships set last_outbound_at = datetime('now', '-8 days'), next_contact_at = datetime('now', '-1 day') where restaurant_id = ?", restaurant_id)

    def mails_to(address):
        return [message for recipients, message in INBOX if recipients == [address]]

    if len(others) < 2:
        print("(skipping 7-8: they need two more restaurants with saved research and qualification)", flush=True)
    else:
        # ------------------------------------------------------------ 7. "No, thank you"
        (no_id, no_name, no_research, no_qualification) = others[0]
        no_address = "notinterested@rawaj-test.example"
        banner(f"7. {no_name} clicks 'No, thank you': the contact stops")
        outcome = start_and_send(no_id, no_research, no_qualification, no_address)
        first = mails_to(no_address)
        check("email 1 was sent to the restaurant", len(first) == 1, str(outcome.get("outreach_errors")))
        decline = re.search(r"no, thank you:\s*(https?://\S+)", plain_text(first[0]), re.I) if first else None
        check("email 1 has the 'No, thank you' link", decline)
        page = requests.get(decline.group(1), timeout=20)
        form = {name: htmllib.unescape(value) for name, value in re.findall(r'name="(token|confirmation)" value="([^"]*)"', page.text)}
        action = urljoin(decline.group(1), htmllib.unescape(re.search(r'<form method="post" action="([^"]*)"', page.text).group(1)))
        requests.post(action, data=form, timeout=90)
        status, opted_out = db("select status, do_not_contact_at from outreach_relationships where restaurant_id = ?", no_id)[0]
        check("the restaurant is marked do-not-contact", status == "DO_NOT_CONTACT" and opted_out, f"status={status}")
        check("no Strategy request was created", db("select count(*) from strategy_requests where restaurant_id = ?", no_id)[0][0] == 0)
        a_week_passes(no_id)
        workflow.run_followups(application_factory=factory)
        workflow.send_reviewed_emails(factory)
        check("nothing more is sent to it, even when a follow-up would be due", len(mails_to(no_address)) == 1)

        # ------------------------------------------------------------ 8. no answer at all
        (quiet_id, quiet_name, quiet_research, quiet_qualification) = others[1]
        quiet_address = "silent@rawaj-test.example"
        banner(f"8. {quiet_name} does not answer: it is followed up")
        start_and_send(quiet_id, quiet_research, quiet_qualification, quiet_address)
        check("email 1 was sent and nothing came back", len(mails_to(quiet_address)) == 1)
        status, attempts, next_contact = db("select status, outreach_attempts, next_contact_at from outreach_relationships where restaurant_id = ?", quiet_id)[0]
        check("it waits for an answer, with the next contact about a week away", status == "WAITING_FOR_RESPONSE" and next_contact, f"{status}, next {next_contact}")
        a_week_passes(quiet_id)
        for attempt in range(1, 4):  # a follow-up the review model rejects is simply tried again on the next pass
            workflow.run_followups(application_factory=factory)
            workflow.send_reviewed_emails(factory)
            if len(mails_to(quiet_address)) > 1:
                break
        types = [t for (t,) in db("select message_type from outbound_messages where restaurant_id = ? order by created_at", quiet_id)]
        print("emails sent to it:", types, flush=True)
        check("a follow-up email was sent", types[-1:] == ["NO_RESPONSE_FOLLOW_UP"] and len(mails_to(quiet_address)) == 2)
        attempts = db("select outreach_attempts from outreach_relationships where restaurant_id = ?", quiet_id)[0][0]
        check("the attempt is counted (so it stops after the maximum and asks a person)", attempts == 2, f"attempts={attempts}")

finally:
    response_server.terminate()
    sink.shutdown()
    banner("SUMMARY")
    for name, ok in results:
        print(("PASS " if ok else "FAIL ") + name)
    passed = sum(ok for _, ok in results)
    print(f"\n{passed}/{len(results)} checks passed" + ("  -> the flow works end to end" if results and passed == len(results) and not ARGS.setup_only else ""), flush=True)
    print(f"(files of this run: {RUN_DIR})")
