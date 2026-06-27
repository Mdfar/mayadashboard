"""Builds and updates the project registry from agy history + trusted workspaces."""
import json, re
from datetime import datetime
from pathlib import Path
from collections import defaultdict

AGY_HISTORY  = Path.home() / ".gemini/antigravity-cli/history.jsonl"
AGY_SETTINGS = Path.home() / ".gemini/antigravity-cli/settings.json"
REGISTRY     = Path(__file__).resolve().parents[1] / "projects" / "registry.json"

def _slug(path: str) -> str:
    name = Path(path).name or "root"
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")

def load_agy_history() -> list:
    if not AGY_HISTORY.exists():
        return []
    entries = []
    for line in AGY_HISTORY.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            entries.append(json.loads(line))
        except Exception:
            pass
    return entries

def load_trusted_workspaces() -> list:
    if not AGY_SETTINGS.exists():
        return []
    try:
        return json.loads(AGY_SETTINGS.read_text(encoding="utf-8")).get("trustedWorkspaces", [])
    except Exception:
        return []

def build_registry() -> dict:
    entries   = load_agy_history()
    trusted   = load_trusted_workspaces()

    ws_data: dict[str, dict] = {}

    for e in entries:
        ws = e.get("workspace", "")
        if not ws or len(ws) < 3:
            continue
        ts = e.get("timestamp", 0) / 1000
        if ws not in ws_data:
            ws_data[ws] = {"count": 0, "last_ts": 0, "samples": []}
        ws_data[ws]["count"] += 1
        if ts > ws_data[ws]["last_ts"]:
            ws_data[ws]["last_ts"] = ts
        if len(ws_data[ws]["samples"]) < 3:
            ws_data[ws]["samples"].append(e.get("display", "")[:120])

    for ws in trusted:
        if ws not in ws_data:
            ws_data[ws] = {"count": 0, "last_ts": 0, "samples": []}

    existing = load_registry()
    existing_by_path = {p["path"]: p for p in existing.get("projects", [])}

    projects = []
    for path, data in sorted(ws_data.items(), key=lambda x: -x[1]["last_ts"]):
        slug = _slug(path)
        prev = existing_by_path.get(path, {})
        last_date = (datetime.fromtimestamp(data["last_ts"]).strftime("%Y-%m-%d")
                     if data["last_ts"] else "")
        projects.append({
            "slug":           prev.get("slug", slug),
            "name":           prev.get("name", Path(path).name or path),
            "path":           path,
            "status":         prev.get("status", "active"),
            "platform":       prev.get("platform", "upwork" if Path(path).exists() else "local"),
            "client":         prev.get("client", ""),
            "notes":          prev.get("notes", ""),
            "next_actions":   prev.get("next_actions", []),
            "last_agy_date":  last_date,
            "agy_msg_count":  data["count"],
            "recent_prompts": data["samples"],
            "created_at":     prev.get("created_at", datetime.now().strftime("%Y-%m-%d")),
        })

    return {"projects": projects, "updated_at": datetime.now().isoformat()}

def load_registry() -> dict:
    if REGISTRY.exists():
        try:
            return json.loads(REGISTRY.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"projects": []}

def save_registry(reg: dict):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False), encoding="utf-8")

def refresh_registry() -> dict:
    reg = build_registry()
    save_registry(reg)
    return reg

if __name__ == "__main__":
    reg = refresh_registry()
    print(f"Registry built: {len(reg['projects'])} projects")
    for p in reg["projects"][:10]:
        print(f"  {p['agy_msg_count']:3d} msgs  {p['last_agy_date']}  {p['name']}")
