import re

with open("tech-leader-assistant/app/tasks.py", "r") as f:
    content = f.read()

tasks = re.findall(r'async def (jira_[a-zA-Z0-9_]+)\(', content)
for task in tasks:
    print(f"Task: {task}")
    # Extract the function body roughly
    start_idx = content.find(f"async def {task}(")
    end_idx = content.find("async def", start_idx + 1)
    if end_idx == -1:
        end_idx = len(content)
    body = content[start_idx:end_idx]

    # Check if it gets comments
    if "jira_client.get_comments" in body:
        print("  - Gets comments")
        # Check how it searches for marker
        lines = body.split("\n")
        for line in lines:
            if "marker in" in line:
                print(f"  - Marker check: {line.strip()}")
