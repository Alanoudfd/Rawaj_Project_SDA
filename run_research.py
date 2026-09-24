import json

from agents.research_agent.research_agent import (
    run_research_agent,
    save_research_profile,
)
from agents.research_agent.research_schemas import RestaurantInfo


# Temporary manual restaurant data for standalone testing
restaurant = RestaurantInfo(
    restaurant_id=6,
    name="Dear Duck",
    instagram_username="dearduck.sa",
    email="hello@dearduck.com",
    location="Jeddah",
)


result = run_research_agent(
    restaurant=restaurant,
    content_limit=20,
    lookback_days=90,
)


print("\n==============================")
print("RESEARCH AGENT FINISHED")
print("==============================\n")

print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))

output_path = save_research_profile(result)
print(f"\nSaved to: {output_path}")
