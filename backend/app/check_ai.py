"""Gate 0 check: does the configured provider and model return a tool call?

Run from the backend folder: python -m app.check_ai

Owner: P3
Plan: section 2
"""
import os
import sys
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    base_url=os.environ["AI_BASE_URL"],
    api_key=os.environ["AI_API_KEY"],
    timeout=30,
)
model = os.environ["AI_MODEL"]

tools = [{
    "type": "function",
    "function": {
        "name": "get_number",
        "description": "Returns the secret number for a label.",
        "parameters": {
            "type": "object",
            "properties": {"label": {"type": "string"}},
            "required": ["label"],
        },
    },
}]

start = time.time()
reply = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Use the tool to get the secret number labelled alpha."}],
    tools=tools,
)
message = reply.choices[0].message

print("model:", model)
print("seconds: %.1f" % (time.time() - start))
if message.tool_calls:
    call = message.tool_calls[0]
    print("tool call returned:", call.function.name, call.function.arguments)
else:
    print("no tool call. text was:", message.content)
    sys.exit(1)
