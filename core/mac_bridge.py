import subprocess
from typing import Optional, List


def run_applescript(script: str) -> str:
    """Executes an AppleScript and returns the output."""
    try:
        process = subprocess.Popen(
            ["osascript", "-e", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if stderr:
            print(f"AppleScript Error: {stderr}")
            return ""
        return stdout.strip()
    except Exception as e:
        print(f"Failed to run AppleScript: {e}")
        return ""


# --- Apple Notes ---


def create_apple_note(title: str, body: str, folder: str = "Notes") -> bool:
    """Creates a new note in Apple Notes."""
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            if not (exists folder "{folder}") then
                make new folder with properties {{name:"{folder}"}}
            end if
            make new note at folder "{folder}" with properties {{name:"{title}", body:"{body}"}}
        end tell
    end tell
    '''
    return run_applescript(script) != ""


def list_apple_notes(folder: str = "Notes") -> List[str]:
    """Lists titles of notes in a folder."""
    script = f'''
    tell application "Notes"
        tell account "iCloud"
            get name of notes of folder "{folder}"
        end tell
    end tell
    '''
    result = run_applescript(script)
    return [n.strip() for n in result.split(",")] if result else []


# --- Apple Clock (Alarms) ---


def set_apple_alarm(label: str, hour: int, minute: int) -> bool:
    """Sets an alarm in the Clock app (macOS Ventura+)."""
    script = f'''
    tell application "Clock"
        make new alarm with properties {{label:"{label}", hour:{hour}, minute:{minute}, enabled:true}}
    end tell
    '''
    return run_applescript(script) != ""


# --- Apple Reminders ---
# (Already handled by iCloud CalDAV, but AppleScript is faster for local check)


def add_apple_reminder(title: str, due_date: Optional[str] = None) -> bool:
    """Adds a reminder via AppleScript."""
    date_clause = f'with properties {{due date:date "{due_date}"}}' if due_date else ""
    script = f'''
    tell application "Reminders"
        make new reminder at end of list "Reminders" with properties {{name:"{title}"}} {date_clause}
    end tell
    '''
    return run_applescript(script) != ""


# --- Apple Mail ---


def send_apple_mail(recipient: str, subject: str, body: str) -> bool:
    """Sends an email using the Mail app."""
    script = f'''
    tell application "Mail"
        set newMessage to make new outgoing message with properties {{subject:"{subject}", content:"{body}", visible:true}}
        tell newMessage
            make new recipient at end of to recipients with properties {{address:"{recipient}"}}
            -- send -- (Commented out to let user verify before sending, or uncomment for auto-send)
        end tell
        activate
    end tell
    '''
    return run_applescript(script) != ""
