import re

with open("tech-leader-assistant/app/tasks.py", "r") as f:
    content = f.read()

# We need to find all instances of `marker in <expr>` or `reminder_marker in <expr>` or `warning_marker in <expr>`
# inside a loop over comments, where it checks for the marker in the comment body.

# It's better to just do it manually for the tasks. Let's list the ones we need to change:
# - jira_epic_missing_due_date_warning_task
# - jira_stale_assigned_task_warning_task
