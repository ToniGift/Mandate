"""Check that the Nebius model can make tool calls.

Run from the repo root:  python scripts/check_nebius.py
Prints only: the model name and whether a tool call came back. Never prints the key.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DUMMY_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


def main() -> None:
    key = os.environ.get("NEBIUS_API_KEY", "")
    model = os.environ.get("NEBIUS_MODEL_ID", "")
    base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/")
    if not key or not model:
        print("NEBIUS_API_KEY and NEBIUS_MODEL_ID must be set in .env")
        return

    print(f"model: {model}")
    try:
        client = OpenAI(base_url=base_url, api_key=key)
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "What is the weather in Warsaw? Use the tool."}],
            tools=[DUMMY_TOOL],
            temperature=0,
        )
    except Exception as err:  # print only the error type, never details
        print(f"request failed: {type(err).__name__}")
        return

    made_call = bool(resp.choices[0].message.tool_calls)
    print(f"tool call returned: {'yes' if made_call else 'no'}")


if __name__ == "__main__":
    main()
