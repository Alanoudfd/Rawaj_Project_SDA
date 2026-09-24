"""Score saved LLM decisions with pass@k and pass^k; no agent or guardrail calls."""


def score_case(case, runs):
    """pass@k: at least one of the k decisions is correct. pass^k: all k decisions are correct."""
    correct = [not r.get("error") and r.get("decision") == case["expected"]["decision"] for r in runs]
    complete = len(runs) == case["k"]
    return {
        "id": case["id"], "expected": case["expected"]["decision"], "k": case["k"],
        "runs": len(runs), "complete": complete, "decisions": [r.get("decision") if not r.get("error") else "ERROR" for r in runs],
        "correct": sum(correct),
        "pass_at_k": any(correct) if complete else None,
        "pass_pow_k": all(correct) if complete else None,
    }


def summarize(scores):
    complete = [s for s in scores if s["complete"]]
    same_k = len({s["k"] for s in complete}) == 1
    return {
        "cases": len(scores), "completed_cases": len(complete),
        "pass_at_k": sum(s["pass_at_k"] for s in complete) / len(complete) if complete and same_k else None,
        "pass_pow_k": sum(s["pass_pow_k"] for s in complete) / len(complete) if complete and same_k else None,
    }
