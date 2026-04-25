"""Windows notification wrapper for heartbeat alerts.

Tries winotify first (cleanest API), then a raw PowerShell WinRT call.
Always uses full powershell.exe path so it works from Task Scheduler and git bash.
Degrades gracefully — never raises on notification failure.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime

_PS_EXE = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"


def send_toast(title: str, message: str, duration: int = 10) -> bool:
    """Send a Windows Toast notification. Returns True if a notifier succeeded."""

    # Primary: winotify (uses PowerShell internally, cleaner API)
    try:
        from winotify import Notification  # type: ignore

        # winotify calls powershell — patch its search to use full path
        import winotify as _wn
        _orig = _wn._run_ps.__code__ if hasattr(_wn, "_run_ps") else None

        toast = Notification(app_id="Second Brain", title=title, msg=message, duration="short")
        # Override powershell path for winotify via env
        import os
        env = os.environ.copy()
        env["PATH"] = r"C:\Windows\System32\WindowsPowerShell\v1.0;" + env.get("PATH", "")
        toast.show()
        return True
    except Exception:
        pass

    # Fallback: raw PowerShell WinRT toast
    try:
        safe_title = title.replace("'", "").replace('"', "")
        safe_msg = message.replace("'", "").replace('"', "")
        ps_script = (
            "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            "ContentType = WindowsRuntime] | Out-Null; "
            "$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
            "$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
            f"$xml.SelectSingleNode('//text()[1]').InnerText = '{safe_title}'; "
            f"$xml.SelectSingleNode('//text()[2]').InnerText = '{safe_msg}'; "
            "$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Second Brain').Show($toast)"
        )
        subprocess.Popen(
            [_PS_EXE, "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        pass

    # Last resort: stderr so the log captures it
    ts = datetime.now().strftime("%H:%M")
    print(f"[{ts}] NOTIFICATION: {title} — {message}", file=sys.stderr)
    return False


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ok = send_toast(sys.argv[1], sys.argv[2])
    else:
        ok = send_toast("Second Brain", "Heartbeat test — if you see this, toasts work.")
    sys.exit(0 if ok else 1)
