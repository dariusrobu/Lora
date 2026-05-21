import json
import os

subagents = {
    "98164cb0-732d-426a-8bff-2fa176824dd6": "API, DB & Scheduler Auditor",
    "320b78fe-6d25-4ad5-b232-9a33749f4fa2": "Gemini & Agent Core Auditor",
    "50f827c4-3525-4fe5-a277-ca3c19dfc813": "Core & Bot Layer Auditor 1",
    "d914d92c-f36b-4fc3-abc3-d4c4edf5f9db": "Core & Bot Layer Auditor 2",
    "3a5f362e-afff-4126-8edc-81ee208361c4": "Modules Auditor 1",
    "4b05f5fe-5fac-4788-898a-8dde70262b22": "Modules Auditor 2",
}

output_path = "/Users/robudarius/Lora/scratch/all_subagent_clean_reports.txt"
with open(output_path, "w") as out:
    for sid, name in subagents.items():
        out.write("\n==================================================\n")
        out.write(f"SUBAGENT: {name} (ID: {sid})\n")
        out.write("==================================================\n")

        path = f"/Users/robudarius/.gemini/antigravity/brain/{sid}/.system_generated/logs/transcript.jsonl"
        if not os.path.exists(path):
            out.write("Transcript does not exist.\n")
            continue

        # Find the last few steps with type PLANNER_RESPONSE or GENERIC from MODEL
        last_model_responses = []
        with open(path, "r") as f:
            for line in f:
                try:
                    step = json.loads(line.strip())
                    if step.get("source") == "MODEL":
                        # We want the content of the response
                        content = step.get("content", "")
                        tool_calls = step.get("tool_calls", [])
                        # If it sent a message to the parent (which is send_message call), let's check its arguments
                        for tc in tool_calls:
                            if tc.get("name") == "send_message":
                                msg = tc.get("args", {}).get("Message", "")
                                if msg:
                                    last_model_responses.append(
                                        f"[MESSAGE TO PARENT]:\n{msg}"
                                    )
                        if content and not tool_calls:
                            last_model_responses.append(f"[TEXT CONTENT]:\n{content}")
                except Exception:
                    pass

        if not last_model_responses:
            out.write("No model responses found.\n")
        else:
            # Write the last 3 model responses (often there's only 1 or 2 final summaries)
            for resp in last_model_responses[-3:]:
                out.write(resp + "\n\n")

print("Finished extracting all reports.")
