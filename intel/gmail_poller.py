"""Gmail poller — pulls Upwork emails, saves to inbox/.
Requires Desktop OAuth2 client JSON at OAUTH_CLIENT path.
First run opens browser for auth; token saved for subsequent runs.
"""
import json, base64, re, threading
from datetime import datetime
from pathlib import Path

OAUTH_CLIENT  = Path.home() / ".secrets/gmail_oauth_desktop.json"
TOKEN_FILE    = Path(__file__).resolve().parent / "gmail_token.json"
INBOX_DIR     = Path(__file__).resolve().parents[1] / "inbox"
SCOPES        = ["https://www.googleapis.com/auth/gmail.readonly"]
POLL_INTERVAL = 180  # seconds

_callback = None  # set by dashboard to receive (subject, from, snippet)

def set_callback(fn):
    global _callback
    _callback = fn

def _get_creds():
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
    except ImportError:
        raise RuntimeError("Run: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client")

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not OAUTH_CLIENT.exists():
                raise FileNotFoundError(
                    f"Gmail OAuth client not found at {OAUTH_CLIENT}\n"
                    "Create a Desktop OAuth2 client in Google Cloud Console → "
                    "APIs & Services → Credentials → Create → Desktop app → download JSON → "
                    f"save to {OAUTH_CLIENT}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(OAUTH_CLIENT), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
    return creds

def _decode_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    for part in payload.get("parts", []):
        result = _decode_body(part)
        if result:
            return result
    return ""

def _parse_message(msg: dict) -> dict:
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    body = _decode_body(msg.get("payload", {}))
    ts_ms = int(msg.get("internalDate", 0))
    ts = datetime.fromtimestamp(ts_ms / 1000).isoformat() if ts_ms else datetime.now().isoformat()
    date_str = datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d") if ts_ms else datetime.now().strftime("%Y-%m-%d")
    return {
        "id":       msg.get("id", ""),
        "ts":       ts,
        "date":     date_str,
        "subject":  headers.get("subject", "(no subject)"),
        "from":     headers.get("from", ""),
        "snippet":  msg.get("snippet", ""),
        "body":     body[:2000],
        "source":   "gmail",
        "platform": "upwork" if "upwork" in headers.get("from", "").lower() else "gmail",
        "action":   _infer_action(headers.get("subject", ""), msg.get("snippet", "")),
    }

def _infer_action(subject: str, snippet: str) -> str:
    s = (subject + " " + snippet).lower()
    if "invitation" in s or "invite" in s:
        return "Review job invitation"
    if "message from" in s or "sent you a message" in s:
        return "Reply to client message"
    if "offer" in s:
        return "Review job offer"
    if "contract" in s and "ended" in s:
        return "Acknowledge contract end"
    if "payment" in s or "paid" in s:
        return "Review payment"
    if "feedback" in s or "review" in s:
        return "Check feedback"
    return "Review email"

def _save_inbox_item(item: dict):
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    fname = INBOX_DIR / f"{item['date']}_{item['id'][:12]}.json"
    if fname.exists():
        return False  # already saved
    fname.write_text(json.dumps(item, indent=2, ensure_ascii=False), encoding="utf-8")
    return True

def poll_once() -> list:
    """Fetch new Upwork emails. Returns list of new items."""
    try:
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError("Run: pip install google-api-python-client")

    creds = _get_creds()
    service = build("gmail", "v1", credentials=creds)

    results = service.users().messages().list(
        userId="me",
        q="from:*@upwork.com OR from:noreply@upwork.com",
        maxResults=20,
    ).execute()

    messages = results.get("messages", [])
    new_items = []
    for m in messages:
        msg = service.users().messages().get(userId="me", id=m["id"], format="full").execute()
        item = _parse_message(msg)
        if _save_inbox_item(item):
            new_items.append(item)
            if _callback:
                _callback(item)
    return new_items

def load_inbox(days: int = 30) -> list:
    """Load inbox items from disk, newest first."""
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for f in INBOX_DIR.glob("*.json"):
        try:
            items.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            pass
    return sorted(items, key=lambda x: x.get("ts", ""), reverse=True)

def start_background_poller(interval: int = POLL_INTERVAL):
    """Start background thread that polls Gmail every `interval` seconds."""
    def _loop():
        import time
        while True:
            try:
                new = poll_once()
                if new and _callback:
                    for item in new:
                        _callback(item)
            except FileNotFoundError:
                pass  # credentials not set up yet
            except Exception as e:
                print(f"[gmail_poller] {e}")
            time.sleep(interval)
    t = threading.Thread(target=_loop, daemon=True)
    t.start()
    return t

def is_configured() -> bool:
    return OAUTH_CLIENT.exists() or TOKEN_FILE.exists()
