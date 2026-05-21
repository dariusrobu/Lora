import json
import os

brain_dir = "/Users/robudarius/.gemini/antigravity/brain"
output_path = "/Users/robudarius/Lora/scratch/all_reports_extracted.txt"

with open(output_path, "w") as out:
    # Find all transcript.jsonl files using os.walk
    paths = []
    for root, dirs, files in os.walk(brain_dir):
        for file in files:
            if file == "transcript.jsonl":
                paths.append(os.path.join(root, file))

    for path in sorted(paths):
        # Extract folder name (conversation ID)
        parts = path.split(os.sep)
        # Find where conv_id is in the path
        # Typically: /Users/robudarius/.gemini/antigravity/brain/<conv_id>/.system_generated/logs/transcript.jsonl
        try:
            brain_idx = parts.index("brain")
            conv_id = parts[brain_idx + 1]
        except Exception:
            conv_id = "unknown"

        out.write(
            "\n======================================================================\n"
        )
        out.write(f"TRANSCRIPT PATH: {path}\n")
        out.write(f"CONVERSATION ID: {conv_id}\n")
        out.write(
            "======================================================================\n"
        )

        # Read the file
        model_messages = []
        user_messages = []

        with open(path, "r") as f:
            for line in f:
                try:
                    step = json.loads(line.strip())
                    source = step.get("source")
                    step_type = step.get("type")
                    content = step.get("content", "")
                    tool_calls = step.get("tool_calls", [])

                    if source == "USER_EXPLICIT" and content:
                        user_messages.append(content)
                    elif source == "MODEL":
                        # If model is sending a message or responding
                        if content and not tool_calls:
                            model_messages.append(content)
                        for tc in tool_calls:
                            if tc.get("name") == "send_message":
                                msg = tc.get("args", {}).get("Message", "")
                                if msg:
                                    model_messages.append(f"[SEND_MESSAGE]: {msg}")
                except Exception:
                    pass

        # Let's print the last user prompt to see the context
        if user_messages:
            out.write(f"LAST USER PROMPT:\n{user_messages[-1][:400]}\n\n")

        # Let's print the last model response(s)
        if model_messages:
            out.write("LAST MODEL RESPONSES:\n")
            for m in model_messages[-2:]:  # last 2 messages
                out.write(f"{m}\n---\n")
        else:
            out.write("No model responses.\n")

print(f"Done. Extracted from {len(paths)} transcripts.")
