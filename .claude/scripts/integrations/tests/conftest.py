"""
conftest.py — adds the .claude/scripts directory to sys.path so that
`from integrations.gcal import ...` works in all tests.
"""
import sys
from pathlib import Path

# .claude/scripts/integrations/tests/ -> .claude/scripts/
scripts_dir = Path(__file__).parent.parent.parent
if str(scripts_dir) not in sys.path:
    sys.path.insert(0, str(scripts_dir))
