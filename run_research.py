from agents.research_agent.research_agent import research_agent
from agents.research_agent.research_models import RestaurantInfo


# Temporary manual restaurant data for standalone testing
restaurant = RestaurantInfo(
    restaurant_id=5,
    name="Casa Myrra",
    instagram_username="casamyrrariyadh",
    email=None,
    location="Riyadh",
)


task = f"""
Research this restaurant:

Restaurant ID: {restaurant.restaurant_id}
Name: {restaurant.name}
Instagram username: {restaurant.instagram_username}
Email: {restaurant.email}
Location: {restaurant.location}

Research settings:
- content_limit: 5
- lookback_days: 90

Run the complete research process using the available research pipeline.
"""


result = research_agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": task,
            }
        ]
    },
    config={
        "recursion_limit": 10,
    },
)


print("\n==============================")
print("RESEARCH AGENT FINISHED")
print("==============================\n")

for message in result["messages"]:
    # Show which tool the agent called
    if getattr(message, "tool_calls", None):
        for tool_call in message.tool_calls:
            print(f"TOOL CALLED: {tool_call['name']}")

    # Show final text response
    if getattr(message, "content", None):
        if type(message).__name__ == "AIMessage":
            print("\nAI:")
            print(message.content)