import re
with open("tests/test_main.py", "r") as f:
    c = f.read()

c = c.replace('mocker.patch("app.clients.settings.get", side_effect=mock_settings_get)', 'mocker.patch("app.main.settings", mock_settings)')

with open("tests/test_main.py", "w") as f:
    f.write(c)
