import json
import os

paths = [
    "/Users/robudarius/.gemini/antigravity/brain/98164cb0-732d-426a-8bff-2fa176824dd6/.system_generated/logs/transcript.jsonl",
    "/Users/robudarius/.gemini/antigravity/brain/320b78fe-6d25-4ad5-b232-9a33749f4fa2/.system_generated/logs/transcript.jsonl",
]

for path in paths:
    print("\n==========================================")
    print(f"PATH: {path}")
    print("==========================================")
    if not os.path.exists(path):
        print("Not found.")
        continue
    with open(path, "r") as f:
        for line in f:
            try:
                step = json.loads(line.strip())
                tool_calls = step.get("tool_calls", [])
                for tc in tool_calls:
                    if tc.get("name") == "send_message":
                        msg = tc.get("args", {}).get("Message", "")
                        print(f"FOUND send_message. Message length: {len(msg)}")
                        # Print first 2000 chars and last 2000 chars
                        if len(msg) > 4000:
                            print("--- BEGINNING ---")
                            print(msg[:2000])
                            print("--- END ---")
                            print(msg[-2000:])
                        else:
                            print(msg)
            except Exception as e:
                print(f"Error parsing line: {e}")
