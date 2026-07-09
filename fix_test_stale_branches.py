with open("tech-leader-assistant/app/main.py", "r") as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith("@app.get(\"/api/stale-branches\")"):
        if i == 182:
            skip = True
            continue
    if skip:
        if line.startswith("class ChatRequest(BaseModel):"):
            skip = False

    if not skip:
        new_lines.append(line)

with open("tech-leader-assistant/app/main.py", "w") as f:
    f.writelines(new_lines)
