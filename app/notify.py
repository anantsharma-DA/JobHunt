"""Windows notifications (the pop-ups in the corner of the screen) for reminders and auto-search results.

They use Windows' own notification system through Windows PowerShell, so nothing extra is installed. The text is
escaped for XML and handed over in an environment variable, never pasted into a command, so a job title can't break
or inject anything.
"""
import json
import os
import subprocess
import sys
from datetime import datetime
from xml.sax.saxutils import escape, quoteattr

from app import errors

# Windows PowerShell's own app id: notifications show under "Windows PowerShell" without registering anything.
APP_ID = r"{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
_SCRIPT = (
    "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null;"
    "[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null;"
    "$x = New-Object Windows.Data.Xml.Dom.XmlDocument; $x.LoadXml($env:JOBHUNT_TOAST_XML);"
    "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($env:JOBHUNT_TOAST_APP)"
    ".Show([Windows.UI.Notifications.ToastNotification]::new($x))"
)
OPEN_APP = "http://localhost:8000/"


def toast_xml(title, text, launch=OPEN_APP):
    """The notification as Windows expects it. Clicking it opens `launch` (JobHunt in your browser)."""
    return (f"<toast activationType=\"protocol\" launch={quoteattr(launch)}><visual><binding template=\"ToastGeneric\">"
            f"<text>{escape(str(title)[:120])}</text><text>{escape(str(text)[:400])}</text>"
            f"</binding></visual></toast>")


def send(title, text, launch=OPEN_APP):
    """Shows one notification. Returns True if it was handed to Windows (or written to the test log)."""
    log = os.environ.get("JOBHUNT_NOTIFY_LOG")
    if log:  # automated tests: record it instead of popping up
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(json.dumps({"title": title, "text": text, "launch": launch, "at": datetime.now().isoformat()}) + "\n")
        return True
    if sys.platform != "win32":
        return False
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _SCRIPT],
            env={**os.environ, "JOBHUNT_TOAST_XML": toast_xml(title, text, launch), "JOBHUNT_TOAST_APP": APP_ID},
            capture_output=True, timeout=30, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError) as exc:
        errors.hidden(exc, "Windows notification")
        return False
    if result.returncode != 0:
        errors.log.warning("Windows notification failed: %s", result.stderr.decode("utf-8", "replace")[:300])
        return False
    return True
