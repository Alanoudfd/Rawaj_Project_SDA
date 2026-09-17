import json

from agents.qualification_agent.qualification_agent import (
    run_qualification_agent,
)


with open(
    "3brews_sa_qualification_input.json",
    "r",
    encoding="utf-8",
) as file:
    evidence = json.load(file)


result = run_qualification_agent(evidence)


print("\n=== QUALIFICATION RESULT ===\n")
print(json.dumps(
    result,
    indent=2,
    ensure_ascii=False,
))