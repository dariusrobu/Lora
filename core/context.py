from datetime import datetime
import pytz
from core.config import TIMEZONE

async def build_context(pool) -> str:
    """
    Returns a formatted string containing a snapshot of all relevant 
    modules for Lora's current turn.
    """
    user_tz = pytz.timezone(TIMEZONE)
    now = datetime.now(user_tz)
    today = now.date()
    
    # Snapshot contents
    # For now, since Phase 4 modules are not built, we use placeholders
    # but the structure is ready for expansion.
    
    snapshot = []
    snapshot.append(f"Today's Date: {today.strftime('%Y-%m-%d (%A)')}")
    snapshot.append(f"Current Time: {now.strftime('%H:%M')}")
    
    # Phase 4+ will populate these
    snapshot.append("\n--- ACTIVE CONTEXT ---")
    snapshot.append("Tasks: [Phase 4: Not yet loaded]")
    snapshot.append("Events Today: [Phase 5: Not yet loaded]")
    snapshot.append("Active Habits: [Phase 5: Not yet loaded]")
    snapshot.append("Recent Notes: [Phase 5: Not yet loaded]")
    snapshot.append("Finance Summary: [Phase 5: Not yet loaded]")
    snapshot.append("Projects: [Phase 5: Not yet loaded]")
    
    return "\n".join(snapshot)
