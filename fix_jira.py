import re

with open("app/tasks.py", "r") as f:
    text = f.read()

# Pattern 1: marker in getattr(...)
text = re.sub(
    r'(?<!in BeautifulSoup\()(marker|reminder_marker|warning_marker|bot_comment_marker|summary_marker) in (getattr\([^)]+\))',
    r'(\1 in \2 or \1 in BeautifulSoup(\2, "html.parser").get_text())',
    text
)

# Pattern 2: marker in comment_body
text = re.sub(
    r'(?<!in BeautifulSoup\()(marker|reminder_marker|warning_marker|bot_comment_marker|summary_marker) in (comment_body)',
    r'(\1 in \2 or \1 in BeautifulSoup(\2, "html.parser").get_text())',
    text
)

# Pattern 3: marker in note.body
text = re.sub(
    r'(?<!in BeautifulSoup\()(marker|reminder_marker|warning_marker|bot_comment_marker|summary_marker) in (note\.body)',
    r'(\1 in \2 or \1 in BeautifulSoup(\2, "html.parser").get_text())',
    text
)

# Pattern 4: marker in (c.body or "")
text = re.sub(
    r'(?<!in BeautifulSoup\()(marker|reminder_marker|warning_marker|bot_comment_marker|summary_marker) in \(([^.]+)\.body or ""\)',
    r'(\1 in (\2.body or "") or \1 in BeautifulSoup(\2.body or "", "html.parser").get_text())',
    text
)

with open("app/tasks.py", "w") as f:
    f.write(text)
