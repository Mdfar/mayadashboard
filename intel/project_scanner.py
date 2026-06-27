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
            "category":       prev.get("category", prev.get("platform", "local")),
            "technologies":   prev.get("technologies", ""),
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

def get_git_info(path: str) -> dict:
    import subprocess
    p = Path(path)
    if not p.exists() or not (p / ".git").exists():
        return {"is_git": False}
        
    try:
        # Get active branch
        branch_res = subprocess.run(["git", "branch", "--show-current"], 
                                    cwd=path, capture_output=True, text=True, timeout=2)
        branch = branch_res.stdout.strip() if branch_res.returncode == 0 else "unknown"
        
        # Get porcelain status (changed files)
        status_res = subprocess.run(["git", "status", "--porcelain"], 
                                    cwd=path, capture_output=True, text=True, timeout=2)
        status_lines = status_res.stdout.splitlines() if status_res.returncode == 0 else []
        
        # Get recent commit log (last 5 commits)
        log_res = subprocess.run(["git", "log", "-n", "5", "--oneline"], 
                                 cwd=path, capture_output=True, text=True, timeout=2)
        log_lines = log_res.stdout.splitlines() if log_res.returncode == 0 else []
        
        return {
            "is_git": True,
            "branch": branch,
            "changed_files": status_lines,
            "recent_commits": log_lines
        }
    except Exception as e:
        return {"is_git": True, "error": str(e)}

def get_project_stats(path: str) -> dict:
    import os
    p = Path(path)
    if not p.exists():
        return {}
        
    file_counts = defaultdict(int)
    total_loc = 0
    total_size = 0
    
    # Exclude common large folders
    exclude_dirs = {".git", ".venv", "node_modules", "build", "dist", "__pycache__"}
    
    try:
        for root, dirs, files in os.walk(p):
            # Prune exclude directories in-place
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                fpath = Path(root) / file
                if fpath.is_symlink():
                    continue
                try:
                    stat = fpath.stat()
                    total_size += stat.st_size
                    ext = fpath.suffix.lower()
                    if ext in {".py", ".js", ".jsx", ".ts", ".tsx", ".html", ".css", ".md", ".json", ".sql", ".sh", ".bat"}:
                        file_counts[ext] += 1
                        
                        # Approximated LOC count
                        if stat.st_size < 1024 * 1024:  # skip files larger than 1MB for safety
                            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                                total_loc += sum(1 for _ in f)
                except Exception:
                    pass
    except Exception:
        pass
        
    return {
        "file_counts": dict(file_counts),
        "total_loc": total_loc,
        "total_size_mb": round(total_size / (1024 * 1024), 2)
    }

if __name__ == "__main__":
    reg = refresh_registry()
    print(f"Registry built: {len(reg['projects'])} projects")
    for p in reg["projects"][:10]:
        print(f"  {p['agy_msg_count']:3d} msgs  {p['last_agy_date']}  {p['name']}")
