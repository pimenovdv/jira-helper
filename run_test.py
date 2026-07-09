import pytest
import sys
sys.exit(pytest.main(['-s', '-v', 'tech-leader-assistant/tests/test_main.py::test_get_stale_branches']))
