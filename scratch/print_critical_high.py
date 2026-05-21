with open("/Users/robudarius/Lora/scratch/clean_reports.txt", "r") as f:
    lines = f.readlines()

print("--- ALL CRITICAL AND HIGH ISSUES ---")
current_block = []
in_block = False

for line in lines:
    # Check if this line starts a critical/high section
    if "CRITICAL" in line or "HIGH" in line:
        if in_block:
            # print previous block
            print("".join(current_block))
            print("-" * 40)
            current_block = []
        in_block = True
        current_block.append(line)
    elif in_block:
        # Check if we should end the block (e.g. new step or separator)
        if "=== STEP" in line or "--- STEP" in line or "====================" in line:
            print("".join(current_block))
            print("-" * 40)
            current_block = []
            in_block = False
        else:
            current_block.append(line)

if in_block and current_block:
    print("".join(current_block))
