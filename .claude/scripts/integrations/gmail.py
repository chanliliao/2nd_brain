"""Gmail OAuth2 integration.

Scopes: gmail.readonly + gmail.compose (drafts only — never gmail.send).
Token is shared with gcal.py; both use the same token file at data/secrets/gmail_token.json.

If you re-auth here after gcal has added calendar.readonly scope, use the combined
SCOPES list from gcal.py so the token covers all services.
"""
import base64
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

TOKEN_PATH = Path(__file__).parent.parent.parent / "data" / "secrets" / "gmail_token.json"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


@dataclass
class GmailConfig:
    client_id: str
    client_secret: str
    token_path: Path = field(default_factory=lambda: TOKEN_PATH)

    @classmethod
    def from_env(cls) -> "GmailConfig":
        load_dotenv()
        client_id = os.getenv("GMAIL_CLIENT_ID", "").strip()
        client_secret = os.getenv("GMAIL_CLIENT_SECRET", "").strip()
        if not client_id:
            raise ValueError("GMAIL_CLIENT_ID is not set in .env")
        if not client_secret:
            raise ValueError("GMAIL_CLIENT_SECRET is not set in .env")
        return cls(client_id=client_id, client_secret=client_secret)


def auth(config: GmailConfig) -> None:
    """Run OAuth2 InstalledAppFlow to obtain and cache token at config.token_path."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)

    config.token_path.parent.mkdir(parents=True, exist_ok=True)
    config.token_path.write_text(creds.to_json())
    print(f"Authenticated. Token saved to {config.token_path}")


def _get_service(config: GmailConfig):
    """Build and return a Gmail API service. Refreshes token if expired."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    if not config.token_path.exists():
        raise RuntimeError(
            f"No token found at {config.token_path}. Run: python gmail.py auth"
        )

    creds = Credentials.from_authorized_user_file(str(config.token_path), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        config.token_path.write_text(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def _get_header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def _decode_body(msg: dict) -> str:
    """Extract plain-text body from a Gmail message resource."""
    payload = msg.get("payload", {})

    def _find_plain(part: dict) -> Optional[str]:
        mime = part.get("mimeType", "")
        if mime == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                padded = data + "=" * (-len(data) % 4)
                return base64.urlsafe_b64decode(padded).decode("utf-8", errors="replace")
        for sub in part.get("parts", []):
            result = _find_plain(sub)
            if result:
                return result
        return None

    return _find_plain(payload) or msg.get("snippet", "")


def needs_reply(message: dict) -> bool:
    """Heuristic: True if the message/thread likely needs a reply.

    Checks:
    - snippet contains a "?" (question directed at user)
    - subject line contains a "?" (question in subject)
    """
    snippet = message.get("snippet", "")
    subject = message.get("subject", "")
    return "?" in snippet or "?" in subject


def list_unread(config: GmailConfig, since: Optional[str] = None) -> list[dict]:
    """Return up to 20 unread inbox threads.

    since: optional ISO date like "2024-01-15" — adds after:YYYY/MM/DD to query.
    Returns list of dicts: {id, subject, snippet, from, date, needs_reply}.
    """
    service = _get_service(config)
    query = "is:unread in:inbox"
    if since:
        date_part = since.replace("-", "/")
        query += f" after:{date_part}"

    result = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=20)
        .execute()
    )
    messages = result.get("messages", [])

    threads: list[dict] = []
    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata",
                 metadataHeaders=["Subject", "From", "Date"])
            .execute()
        )
        headers = msg.get("payload", {}).get("headers", [])
        entry = {
            "id": msg["id"],
            "subject": _get_header(headers, "Subject"),
            "snippet": msg.get("snippet", ""),
            "from": _get_header(headers, "From"),
            "date": _get_header(headers, "Date"),
        }
        entry["needs_reply"] = needs_reply(entry)
        threads.append(entry)

    return threads


def get_thread(config: GmailConfig, thread_id: str) -> dict:
    """Return thread with decoded message bodies.

    Returns: {id, messages: [{subject, from, date, body}]}
    """
    service = _get_service(config)
    thread = service.users().threads().get(userId="me", id=thread_id).execute()

    messages = []
    for msg in thread.get("messages", []):
        headers = msg.get("payload", {}).get("headers", [])
        messages.append({
            "subject": _get_header(headers, "Subject"),
            "from": _get_header(headers, "From"),
            "date": _get_header(headers, "Date"),
            "body": _decode_body(msg),
        })

    return {"id": thread_id, "messages": messages}


def format_context(threads: list[dict]) -> str:
    """Return plain-text summary of threads for LLM context injection."""
    lines = [f"UNREAD GMAIL ({len(threads)} threads):"]
    for t in threads:
        flag = " [NEEDS REPLY]" if t.get("needs_reply") else ""
        lines.append(
            f"- [{t.get('subject', '(no subject)')}] "
            f"from {t.get('from', '?')} on {t.get('date', '?')}: "
            f"{t.get('snippet', '')}{flag}"
        )
    return "\n".join(lines)


def cli_dispatch(args: list[str]) -> None:
    """CLI: auth | unread [--since DATE] | thread THREAD_ID"""
    if not args:
        print("Usage: gmail.py auth | unread [--since YYYY-MM-DD] | thread THREAD_ID")
        return

    subcmd = args[0]
    config = GmailConfig.from_env()

    if subcmd == "auth":
        auth(config)
    elif subcmd == "unread":
        since = None
        if "--since" in args:
            idx = args.index("--since")
            if idx + 1 < len(args):
                since = args[idx + 1]
        threads = list_unread(config, since=since)
        print(format_context(threads))
    elif subcmd == "thread":
        if len(args) < 2:
            print("Usage: gmail.py thread THREAD_ID")
            return
        thread = get_thread(config, args[1])
        print(json.dumps(thread, indent=2))
    else:
        print(f"Unknown subcommand: {subcmd}")
        print("Usage: gmail.py auth | unread [--since YYYY-MM-DD] | thread THREAD_ID")


if __name__ == "__main__":
    import sys
    cli_dispatch(sys.argv[1:])
