"""Run pending Strategy handoff requests created by the Outreach Agent."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from agents.outreach_followup_agent.config import get_settings
from agents.outreach_followup_agent.schemas import StrategyRequestHandoff

from .strategy_agent import generate_and_save_strategy_from_handoff


def process_strategy_requests_once(limit: int = 10) -> dict:
    """
    Process pending Strategy requests once.

    Outreach creates a StrategyRequestHandoff after a verified
    Interested response. This worker consumes the request,
    runs the Strategy Agent, and saves the generated strategy.
    """

    settings = get_settings()

    inbox_dir = Path(settings.strategy_handoff_outbox)
    processed_dir = inbox_dir.parent / "processed"

    inbox_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    request_files = sorted(
        inbox_dir.glob("*.json")
    )[:limit]

    results = []

    for request_path in request_files:
        try:
            payload = json.loads(
                request_path.read_text(encoding="utf-8")
            )

            handoff = StrategyRequestHandoff.model_validate(
                payload
            )

            strategy_result = generate_and_save_strategy_from_handoff(
                handoff
            )

            processed_path = processed_dir / request_path.name

            request_path.replace(processed_path)

            results.append(
                {
                    "strategy_request_id": handoff.strategy_request_id,
                    "restaurant_id": handoff.restaurant_id,
                    "strategy_id": strategy_result["strategy_id"],
                    "status": "STRATEGY_GENERATED_AND_SAVED",
                }
            )

        except Exception as error:
            results.append(
                {
                    "request_file": str(request_path),
                    "status": "FAILED",
                    "error": str(error),
                }
            )

    return {
        "scanned": len(request_files),
        "processed": sum(
            item["status"] == "STRATEGY_GENERATED_AND_SAVED"
            for item in results
        ),
        "failed": sum(
            item["status"] == "FAILED"
            for item in results
        ),
        "items": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run pending Rawaj Strategy requests once."
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum Strategy requests to process.",
    )

    args = parser.parse_args()

    result = process_strategy_requests_once(
        limit=args.limit
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())