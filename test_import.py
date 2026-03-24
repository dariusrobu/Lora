import sys
import os

# Mock dependencies that might require UI
import sys
from unittest.mock import MagicMock
sys.modules["matplotlib"] = MagicMock()
sys.modules["matplotlib.pyplot"] = MagicMock()

try:
    print("🧪 Testing imports...")
    import main
    print("✅ main.py imported successfully")
    from bot.handler import projects_command
    print("✅ projects_command imported successfully")
except Exception as e:
    print(f"❌ Error during import: {e}")
    import traceback
    traceback.print_exc()
