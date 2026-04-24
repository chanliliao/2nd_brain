"""Windows notification wrapper for heartbeat alerts.

Tries win10toast_click first, falls back to win10toast, then a PowerShell
fallback. Degrades gracefully — never raises on notification failure.
"""
from __future__ import annotations

import sys
from datetime import datetime


def send_toast(title: str, message: str, duration: int = 10) -> bool:
    """Send a Windows Toast notification. Returns True if a notifier succeeded."""
    # Primary: win10toast-click (installed per Phase 6 spec)
    try:
        from win10toast_click import ToastNotifier  # type: ignore
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration, threaded=True)
        return True
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback 1: win10toast (without _click)
    try:
        from win10toast import ToastNotifier  # type: ignore
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=duration, threaded=True)
        return True
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback 2: PowerShell BurntToast or WScript popup (headless-safe)
    try:
        import subprocess

        safe_title = title.replace("'", "").replace('"', "")
        safe_msg = message.replace("'", "").replace('"', "")
        ps_cmd = (
            f"[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, "
            f"ContentType = WindowsRuntime] | Out-Null; "
            f"$template = [Windows.UI.Notifications.ToastTemplateType]::ToastText02; "
            f"$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($template); "
            f"$xml.GetElementsByTagName('text')[0].AppendChild($xml.CreateTextNode('{safe_title}')) | Out-Null; "
            f"$xml.GetElementsByTagName('text')[1].AppendChild($xml.CreateTextNode('{safe_msg}')) | Out-Null; "
            f"$toast = [Windows.UI.Notifications.ToastNotification]::new($xml); "
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Second Brain').Show($toast)"
        )
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen(
            ["powershell", "-WindowStyle", "Hidden", "-NonInteractive", "-Command", ps_cmd],
            creationflags=creationflags,
        )
        return True
    except Exception:
        pass

    # Last resort: stderr print so the log captures it
    ts = datetime.now().strftime("%H:%M")
    print(f"[{ts}] NOTIFICATION: {title} — {message}", file=sys.stderr)
    return False


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        ok = send_toast(sys.argv[1], sys.argv[2])
    else:
        ok = send_toast("Second Brain", "Heartbeat test notification — if you see this, toasts work.")
    sys.exit(0 if ok else 1)
