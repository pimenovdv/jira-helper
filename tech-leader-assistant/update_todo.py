import re

with open("todo.md", "r") as f:
    content = f.read()

# I already did the automated code review assistant, so I should mark it as done!
content = content.replace("- [ ] **Automated Code Review Assistant**", "- [x] **Automated Code Review Assistant**")

with open("todo.md", "w") as f:
    f.write(content)
