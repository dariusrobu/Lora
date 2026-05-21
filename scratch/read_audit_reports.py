import json
import os

transcript_path = "/Users/robudarius/.gemini/antigravity/brain/eafe3314-e3e8-418c-84f1-a711fcbc79ac/.system_generated/logs/transcript.jsonl"
output_path = "/Users/robudarius/Lora/scratch/audit_reports.txt"

os.makedirs(os.path.dirname(output_path), exist_ok=True)

reports = []
with open(transcript_path, "r") as f:
    for line in f:
        try:
            step = json.loads(line)
            # Look for messages containing critical audit keywords
            content = step.get("content", "")
            if not content:
                continue
            if "CRITICAL" in content or "HIGH" in content or "SEVERITATE" in content:
                # Avoid printing the command itself
                if "python3 -c" in content:
                    continue
                reports.append(
                    f"--- STEP {step.get('step_index')} (Source: {step.get('source')}) ---\n{content}\n"
                )
        except Exception:
            pass

with open(output_path, "w") as out:
    out.write("\n".join(reports))

print(f"Extracted {len(reports)} entries to {output_path}")
