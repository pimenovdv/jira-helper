from bs4 import BeautifulSoup

with open("app/tasks.py", "r") as f:
    content = f.read()

replacements = {
    'marker in getattr(c, "body", "")': 'marker in getattr(c, "body", "") or marker in BeautifulSoup(getattr(c, "body", ""), "html.parser").get_text()',
    'marker in comment_body': 'marker in comment_body or marker in BeautifulSoup(comment_body, "html.parser").get_text()',
    'reminder_marker in getattr(c, "body", "")': 'reminder_marker in getattr(c, "body", "") or reminder_marker in BeautifulSoup(getattr(c, "body", ""), "html.parser").get_text()',
    'reminder_marker in (c.body or "")': 'reminder_marker in (c.body or "") or reminder_marker in BeautifulSoup((c.body or ""), "html.parser").get_text()',
    'reminder_marker in getattr(n, "body", "")': 'reminder_marker in getattr(n, "body", "") or reminder_marker in BeautifulSoup(getattr(n, "body", ""), "html.parser").get_text()',
    'reminder_marker in note.body': 'reminder_marker in note.body or reminder_marker in BeautifulSoup(note.body, "html.parser").get_text()',
    "marker in getattr(c, 'body', '')": "marker in getattr(c, 'body', '') or marker in BeautifulSoup(getattr(c, 'body', ''), 'html.parser').get_text()",
    "warning_marker in getattr(note, 'body', '')": "warning_marker in getattr(note, 'body', '') or warning_marker in BeautifulSoup(getattr(note, 'body', ''), 'html.parser').get_text()",
    'marker in getattr(note, "body", "")': 'marker in getattr(note, "body", "") or marker in BeautifulSoup(getattr(note, "body", ""), "html.parser").get_text()',
    'marker in note.body': 'marker in note.body or marker in BeautifulSoup(note.body, "html.parser").get_text()'
}

for old, new in replacements.items():
    content = content.replace(old, new)

with open("app/tasks.py", "w") as f:
    f.write(content)
