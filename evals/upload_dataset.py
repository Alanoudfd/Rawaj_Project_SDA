"""Create/refresh the LangSmith dataset used to evaluate the Strategy Agent.

    python -m evals.upload_dataset --dry-run    # show the cases, upload nothing
    python -m evals.upload_dataset              # upload new cases to the LangSmith project in .env

This sends the qualification reports (restaurant names, gaps and evidence) to LangSmith.
Cases already uploaded (same qualification_run_id) are skipped, so it is safe to re-run.
"""

import argparse

from dotenv import load_dotenv

from evals.cases import build_cases

DATASET = "rawaj-strategy-agent"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="print the cases without uploading")
    args = parser.parse_args()

    load_dotenv()
    cases = build_cases()
    if not cases:
        print("No completed qualification runs found in the database.")
        return 1

    if args.dry_run:
        for case in cases:
            ref = case["reference"]
            print(f"{case['name']} (qualification run {case['qualification_run_id']}): "
                  f"{len(ref['high_gaps'])} High, {len(ref['moderate_gaps'])} Moderate gaps")
        return 0

    from langsmith import Client

    client = Client()
    if client.has_dataset(dataset_name=DATASET):
        dataset = client.read_dataset(dataset_name=DATASET)
    else:
        dataset = client.create_dataset(
            DATASET, description="Qualification reports -> 30-day strategy. Reference = the High/Moderate gaps to address."
        )
    known = {(e.metadata or {}).get("qualification_run_id") for e in client.list_examples(dataset_id=dataset.id)}
    new = [case for case in cases if case["qualification_run_id"] not in known]
    if new:
        client.create_examples(
            dataset_id=dataset.id,
            examples=[
                {
                    "inputs": case["inputs"], "outputs": case["reference"],
                    "metadata": {"restaurant": case["name"], "qualification_run_id": case["qualification_run_id"]},
                }
                for case in new
            ],
        )
    print(f"Dataset '{DATASET}': uploaded {len(new)} new case(s), {len(cases) - len(new)} already present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
