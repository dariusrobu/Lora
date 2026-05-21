import json

input_path = "/Users/robudarius/Lora/scratch/audit_reports.txt"
output_path = "/Users/robudarius/Lora/scratch/clean_reports.txt"

with open(input_path, "r") as f:
    content = f.read()

# Let's find all json blobs or messages in the txt
# Since we dumped the content of step objects, some might be raw json or escaped strings.
# Let's decode unicode escapes (like \n, \", etc.) if present.
# We can find all content fields.

clean_lines = []
for line in content.splitlines():
    if "--- STEP" in line:
        clean_lines.append("\n" + line + "\n" + "=" * len(line))
        continue
    # If the line contains json, let's parse it and get the content or message
    if line.strip().startswith("{") and line.strip().endswith("}"):
        try:
            data = json.loads(line.strip())
            msg = data.get("content", "")
            if not msg:
                # check inside tool_calls or other structures
                msg = str(data)
            clean_lines.append(msg)
        except:
            clean_lines.append(line)
    else:
        # decode escapes if any
        try:
            decoded = bytes(line, "utf-8").decode("unicode_escape")
            clean_lines.append(decoded)
        except:
            clean_lines.append(line)

with open(output_path, "w") as out:
    out.write("\n".join(clean_lines))

print("Cleaned reports created.")
