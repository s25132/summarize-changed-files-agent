import asyncio
import random
import sys
import os
from typing import Optional
from copilot import CopilotClient
from copilot.tools import define_tool
from copilot.generated.session_events import SessionEventType
from pydantic import BaseModel, Field

# Define the parameters for the tool using Pydantic
class GetWeatherParams(BaseModel):
    city: str = Field(description="The name of the city to get weather for")


WORKSPACE = os.environ.get("GITHUB_WORKSPACE")
if not WORKSPACE:
    print("GITHUB_WORKSPACE not set")
    sys.exit(1)


def get_token() -> Optional[str]:
    return os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")

# Define a tool that Copilot can call
@define_tool(description="Get the current weather for a city")
async def get_weather(params: GetWeatherParams) -> dict:
    city = params.city
    # In a real app, you'd call a weather API here
    conditions = ["sunny", "cloudy", "rainy", "partly cloudy"]
    temp = random.randint(50, 80)
    condition = random.choice(conditions)
    return {"city": city, "temperature": f"{temp}°F", "condition": condition}

async def main():
    gh_token = get_token()
    if not gh_token:
        print("No token env found (COPILOT_GITHUB_TOKEN/GH_TOKEN/GITHUB_TOKEN).")
        return

    # force standard env vars for CLI/SDK
    os.environ["GH_TOKEN"] = gh_token
    os.environ["COPILOT_GITHUB_TOKEN"] = gh_token

    print("\nUruchamianie Copilot SDK...")
    client = CopilotClient()
    await client.start()

    session = await client.create_session({
        "model": "gpt-4.1",
        "streaming": True,
        "tools": [get_weather],
    })

    def handle_event(event):
        if event.type == SessionEventType.ASSISTANT_MESSAGE_DELTA:
            sys.stdout.write(event.data.delta_content)
            sys.stdout.flush()
        if event.type == SessionEventType.SESSION_IDLE:
            print()

    session.on(handle_event)

    await session.send_and_wait({
        "prompt": "What's the weather like in Seattle and Tokyo?"
    })

    await client.stop()

asyncio.run(main())