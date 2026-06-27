"""Per-project agy history + Claude session parsing."""
import json
from datetime import datetime
from pathlib import Path

AGY_HISTORY    = Path.home() / ".gemini/antigravity-cli/history.jsonl"
CLAUDE_SESSIONS = Path.home() / ".claude/sessions"

def get_project_agy_history(project_path: str, limit: int = 30) -> list:
    """Return recent agy history entries for a project, newest first."""
    if not AGY_HISTORY.exists():
        return []
    entries = []
    for line in AGY_HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
            if obj.get("workspace", "") == project_path:
                ts = obj.get("timestamp", 0) / 1000
                entries.append({
                    "ts":       datetime.fromtimestamp(ts).isoformat() if ts else "",
                    "date":     datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
                    "text":     obj.get("display", ""),
                    "conv_id":  obj.get("conversationId", ""),
                    "source":   "agy",
                })
        except Exception:
            pass
    return sorted(entries, key=lambda x: x["ts"], reverse=True)[:limit]

def get_all_project_history(project_path: str, limit: int = 30) -> list:
    """Merge agy + Claude history for a project, newest first."""
    items = get_project_agy_history(project_path, limit)
    # Claude sessions: look for sessions with matching cwd
    claude_items = _get_claude_sessions(project_path, limit // 2)
    merged = items + claude_items
    return sorted(merged, key=lambda x: x["ts"], reverse=True)[:limit]

def _get_claude_sessions(project_path: str, limit: int = 10) -> list:
    if not CLAUDE_SESSIONS.exists():
        return []
    results = []
    for f in sorted(CLAUDE_SESSIONS.glob("*.jsonl"), key=lambda x: x.stat().st_mtime, reverse=True)[:50]:
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            cwd = ""
            first_msg = ""
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
            for line in lines[:10]:
                try:
                    obj = json.loads(line)
                    if not cwd:
                        cwd = obj.get("cwd", "")
                    if not first_msg:
                        role = obj.get("message", {}).get("role", "")
                        if role == "user":
                            content = obj.get("message", {}).get("content", [])
                            if isinstance(content, list):
                                for c in content:
                                    if isinstance(c, dict) and c.get("type") == "text":
                                        first_msg = c.get("text", "")[:120]
                                        break
                except Exception:
                    pass
            if cwd == project_path and first_msg:
                results.append({
                    "ts":     mtime.isoformat(),
                    "date":   mtime.strftime("%Y-%m-%d %H:%M"),
                    "text":   first_msg,
                    "conv_id": f.stem,
                    "source": "claude",
                })
        except Exception:
            pass
        if len(results) >= limit:
            break
    return results

def get_all_projects_latest() -> dict:
    """Return {workspace: latest_entry} for all projects in agy history."""
    if not AGY_HISTORY.exists():
        return {}
    latest: dict[str, dict] = {}
    for line in AGY_HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
            ws = obj.get("workspace", "")
            if not ws:
                continue
            ts = obj.get("timestamp", 0)
            if ws not in latest or ts > latest[ws].get("timestamp", 0):
                latest[ws] = obj
        except Exception:
            pass
    return latest
