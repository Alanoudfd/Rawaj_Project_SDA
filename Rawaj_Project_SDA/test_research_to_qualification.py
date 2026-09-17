import json

from database.database import SessionLocal
from database.repository import (
    get_latest_research,
    build_qualification_input,
    save_qualification_result,
)

from agents.qualification_agent.qualification_agent import (
    run_qualification_agent,
)


def main():
    db = SessionLocal()

    try:
        # 1. Restaurant already stored in the database
        restaurant_id = 1

        # 2. Get its latest Research Agent run
        research_run = get_latest_research(
            db,
            restaurant_id,
        )

        if research_run is None:
            raise ValueError(
                f"No completed research run found "
                f"for restaurant {restaurant_id}."
            )

        print(
            f"Research Run found: {research_run.id}"
        )

        # 3. Build the compact Research → Qualification handoff
        qualification_input = build_qualification_input(
            research_run
        )

        print("\n=== QUALIFICATION INPUT ===\n")
        print(
            json.dumps(
                qualification_input,
                indent=2,
                ensure_ascii=False,
            )
        )

        # 4. Run the Qualification Agent
        qualification_result = run_qualification_agent(
            qualification_input
        )

        print("\n=== QUALIFICATION RESULT ===\n")
        print(
            json.dumps(
                qualification_result,
                indent=2,
                ensure_ascii=False,
            )
        )

        # 5. Save the result
        qualification_run = save_qualification_result(
            db=db,
            restaurant_id=restaurant_id,
            research_run_id=research_run.id,
            result=qualification_result,
        )

        print("\n=== SAVED TO DATABASE ===")
        print(
            f"Qualification Run ID: "
            f"{qualification_run.id}"
        )
        print(
            f"Research Run ID: "
            f"{qualification_run.research_run_id}"
        )
        print(
            f"Qualification: "
            f"{qualification_run.qualification}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()