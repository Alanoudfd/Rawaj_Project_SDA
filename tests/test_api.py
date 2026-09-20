"""Offline API contract tests; all agent calls use injected deterministic runners.

Run with: python -m unittest discover -s tests -v
"""

from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

with patch("dotenv.load_dotenv", return_value=False):
    from api import main as api_main
    from api.main import create_app
    from database.models import (
        AnalysisJob,
        OutreachEvent,
        QualificationRun,
        ResearchRun,
        Strategy,
    )


class RestaurantApiTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rawaj-api-tests-")
        self.addCleanup(temporary.cleanup)
        database_path = Path(temporary.name) / "api-tests.db"
        self.engine = create_engine(
            f"sqlite:///{database_path.as_posix()}",
            connect_args={"check_same_thread": False},
        )
        self.addCleanup(self.engine.dispose)
        self.workflow_calls = []
        self.draft_calls = []
        self.workflow_result = None
        self.workflow_exception = None
        self.client = self.new_client()

    def new_client(self):
        return self.enterContext(
            TestClient(
                create_app(
                    database_engine=self.engine,
                    workflow_runner=self.run_workflow,
                    outreach_runner=self.run_outreach,
                )
            )
        )

    def run_workflow(
        self, restaurant_id, content_limit, lookback_days, force_refresh, context
    ):
        self.workflow_calls.append(
            {
                "restaurant_id": restaurant_id,
                "content_limit": content_limit,
                "lookback_days": lookback_days,
                "force_refresh": force_refresh,
                "context": context,
            }
        )
        if self.workflow_exception is not None:
            raise self.workflow_exception
        if self.workflow_result is not None:
            return self.workflow_result
        research_id = self.add_research(restaurant_id)
        qualification_id = self.add_qualification(restaurant_id, research_id)
        return {
            "research_run_id": research_id,
            "qualification_run_id": qualification_id,
        }

    def run_outreach(self, data):
        self.draft_calls.append(data)
        return {
            "subject": "A marketing idea for your restaurant",
            "body": "We can help introduce your menu to local customers.",
            "message_type": "initial_outreach",
        }

    def create_restaurant(self, **overrides):
        payload = {
            "name": "مطعم تجربة",
            "instagram_username": "@My_Restaurant",
            "email": "hello@example.com",
            "location": "الرياض",
            "context": {
                "cuisine": "Saudi",
                "target_audience": ["families", "office workers"],
                "goals": "Increase weekday reservations",
            },
        }
        payload.update(overrides)
        response = self.client.post("/api/restaurants", json=payload)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def add_research(self, restaurant_id, *, created_at=None, status="completed"):
        with Session(self.engine) as session:
            research = ResearchRun(
                restaurant_id=restaurant_id,
                status=status,
                full_result={"profile": {"username": "my_restaurant"}},
                created_at=created_at or datetime.utcnow(),
            )
            session.add(research)
            session.commit()
            return research.id

    def add_qualification(
        self, restaurant_id, research_id, *, status="completed", created_at=None
    ):
        gaps = [
            {
                "gap": "Irregular posting",
                "severity": "medium",
                "priority": 1,
                "evidence": ["Long gaps between posts"],
                "recommendation_focus": "Create a weekly content calendar",
            }
        ]
        result = {
            "restaurant": "مطعم تجربة",
            "qualification": "qualified",
            "decision_rationale": "A strong menu with room to improve visibility.",
            "marketing_gaps": gaps,
            "strengths": ["Distinctive menu"],
            "data_limitations": [],
        }
        with Session(self.engine) as session:
            qualification = QualificationRun(
                restaurant_id=restaurant_id,
                research_run_id=research_id,
                status=status,
                qualification=result["qualification"],
                decision_rationale=result["decision_rationale"],
                marketing_gaps=gaps,
                strengths=result["strengths"],
                full_result=result,
                created_at=created_at or datetime.utcnow(),
            )
            session.add(qualification)
            session.commit()
            return qualification.id

    def add_active_job(self, restaurant_id, *, status="running"):
        job_id = str(uuid4())
        with Session(self.engine) as session:
            session.add(
                AnalysisJob(
                    id=job_id,
                    restaurant_id=restaurant_id,
                    active_restaurant_id=restaurant_id,
                    status=status,
                    content_limit=30,
                    lookback_days=90,
                    force_refresh=False,
                    context={},
                )
            )
            session.commit()
        return job_id

    def test_health_and_frontend_cors_preflight(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        for origin in ("http://localhost:3000", "http://localhost:5173"):
            with self.subTest(origin=origin):
                response = self.client.options(
                    "/api/restaurants",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(
                    response.headers["access-control-allow-origin"], origin
                )

    def test_restaurant_creation_normalization_listing_and_context_persistence(self):
        restaurant = self.create_restaurant()
        self.assertEqual(restaurant["instagram_username"], "my_restaurant")
        self.assertEqual(
            restaurant["instagram_url"].rstrip("/"),
            "https://www.instagram.com/my_restaurant",
        )
        self.assertEqual(restaurant["context"]["cuisine"], "Saudi")
        restaurant_id = restaurant["id"]
        response = self.client.get(f"/api/restaurants/{restaurant_id}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["context"], restaurant["context"])

        response = self.client.get("/api/restaurants?offset=0&limit=1")
        self.assertEqual(response.status_code, 200)
        listing = response.json()
        self.assertEqual(listing["total"], 1)
        self.assertEqual((listing["offset"], listing["limit"]), (0, 1))
        self.assertEqual(listing["items"][0]["id"], restaurant_id)
        self.assertEqual(
            self.client.get("/api/restaurants?offset=1&limit=1").json()["items"], []
        )

        # A fresh application must retrieve the saved frontend context from SQL.
        restarted_client = self.new_client()
        response = restarted_client.get(f"/api/restaurants/{restaurant_id}/context")
        self.assertEqual(response.status_code, 200)
        saved = response.json()
        self.assertEqual(saved["restaurant"]["context"], restaurant["context"])
        self.assertIsNone(saved["research"])
        self.assertIsNone(saved["qualification"])
        self.assertIsNone(saved["latest_job"])

    def test_duplicate_handles_are_case_insensitive(self):
        self.create_restaurant()
        response = self.client.post(
            "/api/restaurants",
            json={"name": "Another restaurant", "instagram_username": "MY_RESTAURANT"},
        )
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.client.get("/api/restaurants").json()["total"], 1)

    def test_patch_context_and_nullable_contact_fields(self):
        restaurant = self.create_restaurant()
        url = f"/api/restaurants/{restaurant['id']}"
        response = self.client.patch(
            url,
            json={
                "name": "Updated restaurant",
                "email": None,
                "location": None,
                "context": {"cuisine": "Italian", "budget": 1500},
                "is_active": False,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.client.get(url).json()
        self.assertEqual(saved["name"], "Updated restaurant")
        self.assertIsNone(saved["email"])
        self.assertIsNone(saved["location"])
        self.assertEqual(saved["context"], {"cuisine": "Italian", "budget": 1500})
        self.assertFalse(saved["is_active"])
        response = self.client.post(f"{url}/analyze", json={})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.workflow_calls, [])

    def test_invalid_input_is_rejected_before_running_agents(self):
        restaurant = self.create_restaurant()
        url = f"/api/restaurants/{restaurant['id']}"
        for field in ("name", "context", "is_active"):
            with self.subTest(null_field=field):
                response = self.client.patch(url, json={field: None})
                self.assertEqual(response.status_code, 422, response.text)
        for options in (
            {"content_limit": 0},
            {"content_limit": 101},
            {"lookback_days": 0},
            {"lookback_days": 366},
        ):
            with self.subTest(options=options):
                response = self.client.post(f"{url}/analyze", json=options)
                self.assertEqual(response.status_code, 422, response.text)
        for invalid in (
            {"name": "", "instagram_username": "valid_name"},
            {"name": "Restaurant", "instagram_username": "not a handle"},
            {"name": "Restaurant", "instagram_username": "valid_name", "context": []},
        ):
            with self.subTest(restaurant=invalid):
                response = self.client.post("/api/restaurants", json=invalid)
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.workflow_calls, [])

    def test_missing_resources_return_404(self):
        for method, url, body in (
            ("GET", "/api/restaurants/999999", None),
            ("GET", "/api/restaurants/999999/context", None),
            ("PATCH", "/api/restaurants/999999", {"name": "Missing"}),
            ("POST", "/api/restaurants/999999/analyze", {}),
            ("POST", "/api/restaurants/999999/outreach/draft", {}),
            ("GET", f"/api/jobs/{uuid4()}", None),
        ):
            with self.subTest(method=method, url=url):
                response = self.client.request(method, url, json=body)
                self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(self.workflow_calls, [])
        self.assertEqual(self.draft_calls, [])

    def test_analysis_passes_context_and_settings_and_persists_results(self):
        restaurant = self.create_restaurant()
        restaurant_id = restaurant["id"]
        response = self.client.post(
            f"/api/restaurants/{restaurant_id}/analyze",
            json={"content_limit": 12, "lookback_days": 45, "force_refresh": True},
        )
        self.assertEqual(response.status_code, 202, response.text)
        accepted = response.json()
        self.assertEqual(accepted["status"], "queued")
        UUID(accepted["id"])
        self.assertEqual(len(self.workflow_calls), 1)
        call = self.workflow_calls[0]
        self.assertEqual(call["restaurant_id"], restaurant_id)
        self.assertEqual(call["content_limit"], 12)
        self.assertEqual(call["lookback_days"], 45)
        self.assertIs(call["force_refresh"], True)
        self.assertEqual(call["context"], restaurant["context"])

        # TestClient waits for background tasks, so the persisted job is now done.
        response = self.client.get(f"/api/jobs/{accepted['id']}")
        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertEqual(job["status"], "completed", job)
        self.assertIsNone(job["error"])
        self.assertIsNotNone(job["research_run_id"])
        self.assertIsNotNone(job["qualification_run_id"])
        result = self.client.get(f"/api/restaurants/{restaurant_id}/context").json()
        self.assertEqual(result["research"]["id"], job["research_run_id"])
        self.assertEqual(result["qualification"]["id"], job["qualification_run_id"])
        self.assertEqual(
            result["qualification"]["research_run_id"], result["research"]["id"]
        )
        self.assertEqual(result["latest_job"]["id"], job["id"])
        self.assertEqual(
            result["qualification"]["result"]["qualification"], "qualified"
        )
        with Session(self.engine) as session:
            self.assertIsNone(session.get(AnalysisJob, job["id"]).active_restaurant_id)

    def test_analysis_defaults_and_failed_exception_are_safe_and_retryable(self):
        restaurant = self.create_restaurant()
        restaurant_id = restaurant["id"]
        fake_secret = "unit-test-secret-do-not-expose"
        self.workflow_exception = RuntimeError(f"Provider error: {fake_secret}")
        response = self.client.post(f"/api/restaurants/{restaurant_id}/analyze", json={})
        self.assertEqual(response.status_code, 202, response.text)
        job_id = response.json()["id"]
        response = self.client.get(f"/api/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertEqual(job["status"], "failed")
        self.assertTrue(job["error"])
        self.assertNotIn(fake_secret, response.text)
        self.assertEqual(self.workflow_calls[0]["content_limit"], 30)
        self.assertEqual(self.workflow_calls[0]["lookback_days"], 90)
        self.assertFalse(self.workflow_calls[0]["force_refresh"])
        context = self.client.get(f"/api/restaurants/{restaurant_id}/context")
        self.assertNotIn(fake_secret, context.text)
        self.workflow_exception = None
        response = self.client.post(f"/api/restaurants/{restaurant_id}/analyze", json={})
        self.assertEqual(response.status_code, 202, response.text)
        self.assertEqual(
            self.client.get(f"/api/jobs/{response.json()['id']}").json()["status"],
            "completed",
        )

    def test_workflow_error_result_is_safe(self):
        restaurant = self.create_restaurant()
        fake_secret = "unit-test-provider-credential"
        self.workflow_result = {
            "research_run_id": None,
            "qualification_run_id": None,
            "error": f"Authentication failed: {fake_secret}",
        }
        response = self.client.post(
            f"/api/restaurants/{restaurant['id']}/analyze", json={}
        )
        self.assertEqual(response.status_code, 202, response.text)
        response = self.client.get(f"/api/jobs/{response.json()['id']}")
        self.assertEqual(response.json()["status"], "failed")
        self.assertNotIn(fake_secret, response.text)

    def test_invalid_runner_output_fails_job_and_releases_restaurant(self):
        restaurant = self.create_restaurant()
        for invalid in (None, []):
            with self.subTest(output=invalid):
                self.client.app.state.workflow_runner = lambda **kwargs: invalid
                response = self.client.post(
                    f"/api/restaurants/{restaurant['id']}/analyze", json={}
                )
                self.assertEqual(response.status_code, 202, response.text)
                job_id = response.json()["id"]
                job = self.client.get(f"/api/jobs/{job_id}").json()
                self.assertEqual(job["status"], "failed")
                self.assertTrue(job["error"])
                with Session(self.engine) as session:
                    self.assertIsNone(session.get(AnalysisJob, job_id).active_restaurant_id)

    def test_context_uses_latest_job_results_when_analysis_reuses_older_research(self):
        restaurant = self.create_restaurant()
        restaurant_id = restaurant["id"]
        cached_research = self.add_research(
            restaurant_id, created_at=datetime.utcnow() - timedelta(days=1)
        )
        cached_qualification = self.add_qualification(restaurant_id, cached_research)
        newer_research = self.add_research(restaurant_id)
        self.add_qualification(restaurant_id, newer_research)
        # A later qualification of the cached run must not replace this job's result.
        self.add_qualification(restaurant_id, cached_research)
        self.workflow_result = {
            "research_run_id": cached_research,
            "qualification_run_id": cached_qualification,
        }
        response = self.client.post(
            f"/api/restaurants/{restaurant_id}/analyze", json={}
        )
        self.assertEqual(response.status_code, 202, response.text)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/context").json()
        self.assertEqual(result["latest_job"]["status"], "completed")
        self.assertEqual(result["research"]["id"], cached_research)
        self.assertEqual(result["qualification"]["id"], cached_qualification)

    def test_active_job_blocks_duplicate_analysis_and_context_edits(self):
        restaurant = self.create_restaurant()
        url = f"/api/restaurants/{restaurant['id']}"
        self.add_active_job(restaurant["id"])
        response = self.client.post(f"{url}/analyze", json={})
        self.assertEqual(response.status_code, 409, response.text)
        response = self.client.patch(url, json={"context": {"cuisine": "changed"}})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.workflow_calls, [])
        self.assertEqual(self.client.get(url).json()["context"], restaurant["context"])

    def test_analysis_waits_for_concurrent_context_update_before_taking_snapshot(self):
        restaurant = self.create_restaurant()
        url = f"/api/restaurants/{restaurant['id']}"
        new_context = {"cuisine": "Italian", "goals": "Promote the new lunch menu"}
        patch_checked_idle = Event()
        release_patch = Event()
        analyze_requested = Event()
        original_require_idle = api_main.require_idle

        def pause_first_idle_check(db, restaurant_id):
            original_require_idle(db, restaurant_id)
            if not patch_checked_idle.is_set():
                patch_checked_idle.set()
                if not release_patch.wait(5):
                    raise RuntimeError("Timed out waiting to release the context update")

        def submit_analysis():
            analyze_requested.set()
            return self.client.post(f"{url}/analyze", json={})

        with patch("api.main.require_idle", side_effect=pause_first_idle_check):
            with ThreadPoolExecutor(max_workers=2) as executor:
                patch_future = executor.submit(
                    self.client.patch, url, json={"context": new_context}
                )
                try:
                    self.assertTrue(patch_checked_idle.wait(5))
                    analysis_future = executor.submit(submit_analysis)
                    self.assertTrue(analyze_requested.wait(5))
                    # The update has checked for a job but has not written yet.
                    # Starting analysis now must wait rather than copy the old data.
                    with self.assertRaises(TimeoutError):
                        analysis_future.result(timeout=0.25)
                finally:
                    release_patch.set()
                updated = patch_future.result(timeout=5)
                accepted = analysis_future.result(timeout=5)
        self.assertEqual(updated.status_code, 200, updated.text)
        self.assertEqual(accepted.status_code, 202, accepted.text)
        self.assertEqual(self.workflow_calls[0]["context"], new_context)

    def test_startup_recovers_unfinished_jobs_and_releases_restaurant(self):
        restaurant = self.create_restaurant()
        job_id = self.add_active_job(restaurant["id"], status="queued")
        restarted_client = self.new_client()
        response = restarted_client.get(f"/api/jobs/{job_id}")
        self.assertEqual(response.status_code, 200)
        job = response.json()
        self.assertEqual(job["status"], "failed")
        self.assertIsNotNone(job["finished_at"])
        with Session(self.engine) as session:
            self.assertIsNone(session.get(AnalysisJob, job_id).active_restaurant_id)
        response = restarted_client.post(
            f"/api/restaurants/{restaurant['id']}/analyze", json={}
        )
        self.assertEqual(response.status_code, 202, response.text)

    def test_context_qualification_matches_latest_research_and_restaurant(self):
        restaurant = self.create_restaurant()
        restaurant_id = restaurant["id"]
        old_research = self.add_research(
            restaurant_id, created_at=datetime.utcnow() - timedelta(days=1)
        )
        self.add_qualification(restaurant_id, old_research)
        latest_research = self.add_research(restaurant_id)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/context").json()
        self.assertEqual(result["research"]["id"], latest_research)
        self.assertIsNone(result["qualification"])

        # Even inconsistent imported records must not leak another restaurant's data.
        other_restaurant = self.create_restaurant(instagram_username="other_restaurant")
        self.add_qualification(other_restaurant["id"], latest_research)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/context").json()
        self.assertIsNone(result["qualification"])

        matching_qualification = self.add_qualification(restaurant_id, latest_research)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/context").json()
        self.assertEqual(result["qualification"]["id"], matching_qualification)
        self.assertEqual(result["qualification"]["research_run_id"], latest_research)

    def test_gaps_endpoint_counts_severity_tiers(self):
        restaurant_id = self.create_restaurant()["id"]
        self.assertEqual(self.client.get("/api/restaurants/999/gaps").status_code, 404)
        empty = self.client.get(f"/api/restaurants/{restaurant_id}/gaps").json()
        self.assertEqual(empty["counts"]["total"], 0)
        self.assertEqual(empty["gaps"], [])

        research_id = self.add_research(restaurant_id)
        self.add_qualification(restaurant_id, research_id)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/gaps").json()
        self.assertEqual(result["restaurant_id"], restaurant_id)
        self.assertEqual(result["counts"], {"total": 1, "high": 0, "moderate": 1, "low": 0, "strengths": 1, "data_limitations": 0})
        self.assertEqual(result["strengths"], ["Distinctive menu"])
        self.assertEqual(result["gaps"][0]["severity"], "Medium")
        self.assertEqual(result["gaps"][0]["gap"], "Irregular posting")

        # A newer research run without a qualification still shows the last completed gaps.
        self.add_research(restaurant_id)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/gaps").json()
        self.assertEqual(result["counts"]["total"], 1)

    def add_agent_strategy(self, restaurant_id, **extra):
        data = {
            "restaurant": "Agent Cafe",
            "primary_marketing_gaps": [
                {"gap": "Posting gap", "severity": "High", "highlight": 0.47,
                 "highlight_label": "posts/week", "key_point": "Too few posts."},
            ],
            "thirty_day_target": ["Post twice a week", "  "],
            "recommended_services": [{"service": "Content Calendar", "why_this_service_fits": "Fixes cadence."}],
            "thirty_day_plan": [
                {"day": 2, "focus": "Menu", "action": "Show the menu."},
                {"day": 1, "focus": "Kickoff", "action": "Audit the profile."},
                {"day": 1, "focus": "Duplicate", "action": "Ignored."},
                {"day": "x", "focus": "Bad", "action": "Ignored."},
            ],
            "external_trend_support": [],
            **extra,
        }
        with Session(self.engine) as session:
            strategy = Strategy(restaurant_id=restaurant_id, strategy_data=data)
            session.add(strategy)
            session.commit()
            return strategy.id

    def test_agent_strategy_is_read_dated_and_tracks_completed_days(self):
        restaurant_id = self.create_restaurant()["id"]
        self.assertEqual(self.client.get("/api/restaurants/999/agent-strategy").status_code, 404)
        self.assertEqual(self.client.get(f"/api/restaurants/{restaurant_id}/agent-strategy").status_code, 404)

        # A template plan (no thirty_day_plan) is not an agent strategy.
        with Session(self.engine) as session:
            session.add(Strategy(restaurant_id=restaurant_id, strategy_data={"month": "2026-09", "tasks": []}))
            session.commit()
        self.assertEqual(self.client.get(f"/api/restaurants/{restaurant_id}/agent-strategy").status_code, 404)

        self.add_agent_strategy(restaurant_id, strategy_start_date="2026-09-25")
        result = self.client.get(f"/api/restaurants/{restaurant_id}/agent-strategy").json()
        self.assertEqual((result["start_date"], result["end_date"]), ("2026-09-25", "2026-09-26"))
        self.assertEqual([(d["day"], d["date"], d["focus"], d["status"]) for d in result["days"]],
                         [(1, "2026-09-25", "Kickoff", "Planned"), (2, "2026-09-26", "Menu", "Planned")])
        self.assertEqual(result["targets"], ["Post twice a week"])
        self.assertEqual(result["gaps"][0]["highlight"], "0.47")
        self.assertEqual(result["services"][0]["service"], "Content Calendar")

        url = f"/api/restaurants/{restaurant_id}/agent-strategy/days/2"
        result = self.client.patch(url, json={"status": "Completed"}).json()
        self.assertEqual([d["status"] for d in result["days"]], ["Planned", "Completed"])
        # Persisted, and undoable.
        again = self.new_client().get(f"/api/restaurants/{restaurant_id}/agent-strategy").json()
        self.assertEqual([d["status"] for d in again["days"]], ["Planned", "Completed"])
        result = self.client.patch(url, json={"status": "Planned"}).json()
        self.assertEqual([d["status"] for d in result["days"]], ["Planned", "Planned"])

        self.assertEqual(self.client.patch(url.replace("/2", "/9"), json={"status": "Completed"}).status_code, 404)
        self.assertEqual(self.client.patch(url, json={"status": "Done"}).status_code, 422)

    def test_agent_strategy_without_start_date_uses_creation_date(self):
        restaurant_id = self.create_restaurant()["id"]
        self.add_agent_strategy(restaurant_id)
        result = self.client.get(f"/api/restaurants/{restaurant_id}/agent-strategy").json()
        self.assertEqual(result["start_date"], datetime.utcnow().date().isoformat())

    def test_outreach_requires_email_and_completed_current_qualification(self):
        restaurant = self.create_restaurant(email=None)
        restaurant_id = restaurant["id"]
        url = f"/api/restaurants/{restaurant_id}"
        response = self.client.post(f"{url}/outreach/draft", json={})
        self.assertEqual(response.status_code, 422, response.text)
        self.client.patch(url, json={"email": "hello@example.com"})
        response = self.client.post(f"{url}/outreach/draft", json={})
        self.assertEqual(response.status_code, 409, response.text)
        research_id = self.add_research(restaurant_id)
        self.add_qualification(restaurant_id, research_id, status="failed")
        response = self.client.post(f"{url}/outreach/draft", json={})
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual(self.draft_calls, [])

    def test_outreach_builds_draft_from_restaurant_without_sending(self):
        restaurant = self.create_restaurant()
        restaurant_id = restaurant["id"]
        research_id = self.add_research(restaurant_id)
        self.add_qualification(restaurant_id, research_id)
        with patch("smtplib.SMTP") as smtp, patch("smtplib.SMTP_SSL") as smtp_ssl:
            response = self.client.post(
                f"/api/restaurants/{restaurant_id}/outreach/draft", json={}
            )
            self.assertEqual(response.status_code, 200, response.text)
            smtp.assert_not_called()
            smtp_ssl.assert_not_called()
        self.assertEqual(len(self.draft_calls), 1)
        supplied = self.draft_calls[0]
        self.assertEqual(supplied["restaurant_name"], restaurant["name"])
        self.assertEqual(supplied["email"], restaurant["email"])
        self.assertTrue(supplied["marketing_gaps"])
        self.assertTrue(all(isinstance(gap, str) for gap in supplied["marketing_gaps"]))
        self.assertIn("Irregular posting", " ".join(supplied["marketing_gaps"]))
        self.assertIsInstance(supplied["qualification_summary"], str)
        self.assertIn("visibility", supplied["qualification_summary"])
        self.assertEqual(response.json()["subject"], "A marketing idea for your restaurant")
        self.assertTrue(response.json()["body"])
        with Session(self.engine) as session:
            sent_count = session.scalar(
                select(func.count()).select_from(OutreachEvent).where(
                    OutreachEvent.status == "sent"
                )
            )
            self.assertEqual(sent_count, 0)


if __name__ == "__main__":
    unittest.main()
