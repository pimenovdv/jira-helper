with open("tech-leader-assistant/todo.md", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if "Agentic RAG Router" in line:
        line = line.replace("[ ]", "[x]")
    if "Agent-Planner" in line:
        line = line.replace("[ ]", "[x]")
    new_lines.append(line)

with open("tech-leader-assistant/todo.md", "w") as f:
    f.writelines(new_lines)
