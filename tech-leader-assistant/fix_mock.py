import re
with open("tests/test_main.py", "r") as f:
    content = f.read()

content = content.replace('mocker.patch("app.main.settings.get", side_effect=mock_settings_get)', 'mocker.patch("app.clients.settings.get", side_effect=mock_settings_get)')

with open("tests/test_main.py", "w") as f:
    f.write(content)
