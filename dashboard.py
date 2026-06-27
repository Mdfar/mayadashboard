#!/usr/bin/env python3
"""MAYA — Antigravity AI Dashboard (light theme, interactive)"""

import customtkinter as ctk
import subprocess, json, os, shutil, threading, queue, re, uuid, time, sys, webbrowser
from datetime import datetime
from pathlib import Path
from PIL import Image

# ── Intel module (project intelligence) ───────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from intel.project_scanner import load_registry, refresh_registry, save_registry
    from intel.agy_parser import get_all_project_history
    from intel.gmail_poller import load_inbox, start_background_poller, is_configured
    from intel.context_builder import write_context
    HAS_INTEL = True
except Exception as _intel_err:
    HAS_INTEL = False
    def load_registry(): return {"projects": []}
    def refresh_registry(): return {"projects": []}
    def save_registry(r): pass
    def get_all_project_history(p, limit=20): return []
    def load_inbox(days=30): return []
    def start_background_poller(): pass
    def is_configured(): return False
    def write_context(): pass

try:
    import markdown as md_lib
    from tkinterweb import HtmlFrame
    HAS_RENDER = True
except ImportError:
    HAS_RENDER = False

ANSI_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# ── Paths (portable — relative to this file) ──────────────────────────────────

import sys
import os

if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    BASE_DIR = Path(os.path.dirname(sys.executable))
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    BASE_DIR = BUNDLE_DIR

CONTENT_DIR   = BASE_DIR / "content"
ICON_DIR      = BUNDLE_DIR / "assets" / "icons"
SETTINGS_FILE = BASE_DIR / "settings.json"
BACKUP_DIR    = CONTENT_DIR / ".backups"
WIN_SIZE      = "1480x920"
APP_TITLE     = "MAYA"

CONTENT_DIR.mkdir(parents=True, exist_ok=True)

def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def pretty_date(ds: str) -> str:
    try:
        return datetime.strptime(ds, "%Y-%m-%d").strftime("%B %d, %Y")
    except Exception:
        return ds

TODAY = pretty_date(today_str())

FILE_NAMES = {
    "plan": "plan.json", "activities": "activities.json",
    "lessons": "lessons.json", "top_picks": "top_picks.md",
    "discourse": "discourse.md", "outline": "outline.md",
    "draft": "draft.md", "review": "review.md",
}

def date_dir(ds: str) -> Path:
    d = CONTENT_DIR / ds
    d.mkdir(parents=True, exist_ok=True)
    return d

def path_for(kind: str, ds: str) -> Path:
    return date_dir(ds) / FILE_NAMES[kind]

def list_history_dates() -> list:
    """All dated folders, newest first."""
    out = []
    for p in CONTENT_DIR.iterdir():
        if p.is_dir() and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            out.append(p.name)
    return sorted(out, reverse=True)

def migrate_flat_files():
    """Move legacy content/<file> into content/<today>/ once."""
    td = today_str()
    for kind, fn in FILE_NAMES.items():
        flat = CONTENT_DIR / fn
        dest = path_for(kind, td)
        if flat.exists() and not dest.exists():
            try:
                dest.write_bytes(flat.read_bytes())
                flat.unlink()
            except Exception:
                pass

migrate_flat_files()

# ── Palettes (light / dark) ────────────────────────────────────────────────────

_LIGHT = dict(
    BG="#FAF6EC", BG2="#F2EBD8", CARD="#FFFFFF", CARD2="#FBF7EC",
    BORDER="#E6DCC2", INK="#1A2B4A", INK2="#3B4A66", DIM="#9A917D",
    BLUE="#3B6EA5", BLUE_DK="#2C5685", BLUE_SOFT="#E4ECF5",
    YOLK="#F5B82E", YOLK_DK="#E0A312", YOLK_SOFT="#FBEFCB",
    GREEN="#3FA66B", GREEN_DK="#2F8A55", GREEN_SOFT="#E0F0E6",
    RED="#D9544D", RED_SOFT="#F7E2E0", SHADOW="#EFE7D2",
)
_DARK = dict(
    BG="#111827", BG2="#1A2338", CARD="#1E2A3B", CARD2="#243148",
    BORDER="#2D3D5A", INK="#E8EDF5", INK2="#9BACC8", DIM="#5A6B8A",
    BLUE="#4B8FD0", BLUE_DK="#3A7ABB", BLUE_SOFT="#1A2D45",
    YOLK="#F5B82E", YOLK_DK="#E0A312", YOLK_SOFT="#2D2510",
    GREEN="#3FA66B", GREEN_DK="#2F8A55", GREEN_SOFT="#102B1A",
    RED="#E05050", RED_SOFT="#2D1210", SHADOW="#0A1020",
)

def _raw_theme() -> str:
    try:
        raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else {}
        return raw.get("theme", "light")
    except Exception:
        return "light"

_THEME_NAME = _raw_theme()
_pal = _DARK if _THEME_NAME == "dark" else _LIGHT

BG        = _pal["BG"];      BG2       = _pal["BG2"]
CARD      = _pal["CARD"];    CARD2     = _pal["CARD2"]
BORDER    = _pal["BORDER"];  INK       = _pal["INK"]
INK2      = _pal["INK2"];    DIM       = _pal["DIM"]
BLUE      = _pal["BLUE"];    BLUE_DK   = _pal["BLUE_DK"];  BLUE_SOFT = _pal["BLUE_SOFT"]
YOLK      = _pal["YOLK"];    YOLK_DK   = _pal["YOLK_DK"];  YOLK_SOFT = _pal["YOLK_SOFT"]
GREEN     = _pal["GREEN"];   GREEN_DK  = _pal["GREEN_DK"]; GREEN_SOFT= _pal["GREEN_SOFT"]
RED       = _pal["RED"];     RED_SOFT  = _pal["RED_SOFT"]; SHADOW    = _pal["SHADOW"]

ctk.set_appearance_mode("dark" if _THEME_NAME == "dark" else "light")
ctk.set_default_color_theme("blue")

FONT_HEAD = "Segoe UI Semibold"
FONT_BODY = "Segoe UI"

# ── Settings ──────────────────────────────────────────────────────────────────

PLAN_SCHEMA = (
    '{"date":"'+TODAY+'","sections":[{"name":"Morning",'
    '"tasks":[{"id":"t1","title":"Task text","done":false,"priority":"high"}]},'
    '{"name":"Afternoon","tasks":[]},{"name":"Evening","tasks":[]}]}'
)
ACT_SCHEMA = (
    '{"tasks":[{"id":"a1","title":"Task","status":"active","note":""}],'
    '"recommendations":["tip 1","tip 2","tip 3"]}'
)
LES_SCHEMA = (
    '{"date":"'+TODAY+'","lessons":[{"id":"l1","title":"Lesson title",'
    '"what":"3-5 sentence explanation of the concept","'
    'example":"a concrete code snippet or worked example","'
    'action":"one concrete actionable takeaway","learned":false}]}'
)
TOP_PICKS_SCHEMA = (
    "For each entry, generate a beautiful HTML card using the classes: "
    "'pick-card', 'pick-title', 'pick-meta', 'pick-meta-item', 'pick-section', 'pick-section-title', "
    "'pick-summary', 'pick-why', 'pick-tags', and 'pick-tag'. "
    "Use exactly this structure for each entry:\n"
    "<div class=\"pick-card\">\n"
    "  <div class=\"pick-title\">🔥 EMOJI HEADLINE</div>\n"
    "  <div class=\"pick-meta\">\n"
    "    <span class=\"pick-meta-item\">📅 Date: YYYY-MM-DD</span>\n"
    "    <span class=\"pick-meta-item\">🌐 Source: Source Name</span>\n"
    "  </div>\n"
    "  <div class=\"pick-section\">\n"
    "    <div class=\"pick-section-title\">Summary</div>\n"
    "    <div class=\"pick-summary\">Detailed 2-3 sentence summary.</div>\n"
    "  </div>\n"
    "  <div class=\"pick-why\">\n"
    "    <strong>Why it matters:</strong> 1-2 sentences on industry impact and significance.\n"
    "  </div>\n"
    "  <div class=\"pick-tags\">\n"
    "    <span class=\"pick-tag\">#tag1</span>\n"
    "    <span class=\"pick-tag\">#tag2</span>\n"
    "  </div>\n"
    "</div>\n"
)

def _detect_agy() -> str:
    # 1. Environment Variable
    env = os.environ.get("AGY_PATH")
    if env and Path(env).exists():
        return env
        
    # 2. Check System PATH
    which = shutil.which("agy")
    if which:
        return which
        
    # 3. Check App Data directory (Gemini CLI install default)
    app_data_path = Path.home() / ".gemini/antigravity-cli/bin/agy.exe"
    if app_data_path.exists():
        return str(app_data_path)
    app_data_path2 = Path.home() / ".gemini/antigravity-cli/agy.exe"
    if app_data_path2.exists():
        return str(app_data_path2)
        
    # 4. Check relative to current Python executable scripts folder (venv)
    py_exe_dir = Path(sys.executable).parent
    if (py_exe_dir / "agy.exe").exists():
        return str(py_exe_dir / "agy.exe")
    if (py_exe_dir / "Scripts/agy.exe").exists():
        return str(py_exe_dir / "Scripts/agy.exe")
    if (py_exe_dir / "bin/agy").exists():
        return str(py_exe_dir / "bin/agy")
        
    # 5. Check local project .venv directory
    local_venv_win = Path(BASE_DIR) / ".venv" / "Scripts" / "agy.exe"
    if local_venv_win.exists():
        return str(local_venv_win)
    local_venv_unix = Path(BASE_DIR) / ".venv" / "bin" / "agy"
    if local_venv_unix.exists():
        return str(local_venv_unix)
        
    # 6. Check common global AppData Local Python directories (Windows)
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        p = Path(local_app_data) / "Programs/Python"
        if p.exists():
            for scripts_dir in p.glob("**/Scripts/agy.exe"):
                return str(scripts_dir)

    fallback = Path.home() / ".gemini/antigravity-cli/bin/agy.exe"
    return str(fallback)

DEFAULT_SETTINGS = {
    "font_size": 16,
    "font_face": "Segoe UI",
    "theme": "light",
    "agy_path": _detect_agy(),
    "model": "gemini-3.5-flash",
    "auto_generate": True,
    "top_picks_instruction": "Research the 5 most important AI and tech developments for today.",
    "plan_instruction": "Create a daily plan for a software engineer/AI developer for today.",
    "activities_instruction": "Read the target file if it exists, preserve its tasks, then update it. Add 3 useful recommendations based on the tasks.",
    "lessons_instruction": "Write exactly 10 in-depth lessons (like a tutorial chapter, e.g. w3schools style) for a software engineer working on AI today. Each lesson needs a clear explanation (what), a concrete worked example (example), and one actionable takeaway (action).",
    "wp_url": "https://yourblog.com",
    "wp_username": "admin",
    "wp_app_password": "",
    "ghost_url": "https://yourblog.ghost.io",
    "ghost_admin_api_key": "",
    "git_repo_path": "",
}

SETTINGS: dict = {}

def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return {**DEFAULT_SETTINGS, **json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))}
        except Exception:
            pass
    return dict(DEFAULT_SETTINGS)

def save_settings(s: dict):
    SETTINGS_FILE.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    SETTINGS.update(s)

SETTINGS.update(load_settings())

def agy_exe() -> Path:
    return Path(SETTINGS.get("agy_path", _detect_agy()))

_MODEL_ID_MAP = {
    "Gemini 3.5 Flash (Low)":    "gemini-3.5-flash-low",
    "Gemini 3.5 Flash (Medium)": "gemini-3.5-flash-medium",
    "Gemini 3.5 Flash (High)":   "gemini-3.5-flash-high",
    "Gemini 3.1 Pro (Low)":      "gemini-3.1-pro-low",
    "Gemini 3.1 Pro (High)":     "gemini-3.1-pro-high",
}

def agy_model() -> str:
    """Return the real API model ID that agy --model accepts."""
    display = SETTINGS.get("model", "gemini-3.5-flash")
    # If it's already an API id (contains a dash), use as-is
    if "-" in display:
        return display
    return _MODEL_ID_MAP.get(display, "gemini-3.5-flash")

def build_prompt(instruction: str, kind: str, ds: str) -> tuple:
    """Attach the concrete, date-correct target file path and schema to a user instruction."""
    target = path_for(kind, ds)
    schema_map = {
        "top_picks": f"Write raw HTML directly to the target file. Do not wrap in markdown backticks. Overwrite the file completely. Do not explain, just write it.\n{TOP_PICKS_SCHEMA}",
        "plan": f"Write JSON using EXACTLY this schema: {PLAN_SCHEMA} . Sections: Morning, Afternoon, Evening. priority is one of high|medium|low. id must be unique. Output ONLY valid JSON to the target file. Do not explain.",
        "activities": f"Write JSON using EXACTLY this schema: {ACT_SCHEMA} . status is one of active|pending|done|blocked. Add 3 useful recommendations based on the tasks. Output ONLY valid JSON to the target file. Do not explain.",
        "lessons": f"Write JSON using EXACTLY this schema: {LES_SCHEMA} . learned is always false initially. id unique. Output ONLY valid JSON to the target file. Do not explain."
    }
    system_instr = schema_map.get(kind, "")
    full_prompt = f"{instruction} {system_instr}\n\nTARGET FILE (write here, overwrite it): {target}"
    return full_prompt, instruction

# Set by DashboardApp at startup; gives tabs access to current_date + toast().
APP = None

# ── JSON store helpers ─────────────────────────────────────────────────────────

def load_json(path: Path, default):
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if default is None or type(data) is type(default):
                return data
    except Exception:
        pass
    return default

def save_json(path: Path, data) -> float:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        return path.stat().st_mtime
    except Exception:
        return 0.0

def new_id() -> str:
    return uuid.uuid4().hex[:8]

# ── Validation / normalization ─────────────────────────────────────────────────

_PRIORITIES = {"high", "medium", "low"}
_STATUSES   = {"active", "pending", "done", "blocked"}

def validate_and_fix(kind: str, data):
    """Return (ok, normalized_data, message). ok=False => keep old data, show toast."""
    try:
        if kind == "plan":
            if not isinstance(data, dict) or not isinstance(data.get("sections"), list):
                return False, None, "plan.json: missing 'sections' list"
            for s in data["sections"]:
                if not isinstance(s, dict):
                    return False, None, "plan.json: bad section"
                s.setdefault("name", "Section")
                tasks = s.get("tasks")
                if not isinstance(tasks, list):
                    s["tasks"] = tasks = []
                for t in tasks:
                    t.setdefault("id", new_id())
                    t.setdefault("title", "")
                    t["done"] = bool(t.get("done", False))
                    if t.get("priority") not in _PRIORITIES:
                        t["priority"] = "medium"
            return True, data, ""
        if kind == "activities":
            if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
                return False, None, "activities.json: missing 'tasks' list"
            for t in data["tasks"]:
                t.setdefault("id", new_id())
                t.setdefault("title", "")
                t.setdefault("note", "")
                if t.get("status") not in _STATUSES:
                    t["status"] = "active"
            if not isinstance(data.get("recommendations"), list):
                data["recommendations"] = []
            return True, data, ""
        if kind == "lessons":
            if not isinstance(data, dict) or not isinstance(data.get("lessons"), list):
                return False, None, "lessons.json: missing 'lessons' list"
            for l in data["lessons"]:
                l.setdefault("id", new_id())
                l.setdefault("title", "")
                l.setdefault("what", "")
                l.setdefault("example", "")
                l.setdefault("action", "")
                l["learned"] = bool(l.get("learned", False))
            return True, data, ""
    except Exception as e:
        return False, None, f"{kind}: {e}"
    return True, data, ""

# ── Backups ────────────────────────────────────────────────────────────────────

def backup_file(path: Path, keep: int = 20):
    """Snapshot a file into content/.backups before overwrite. Keep last N per stem."""
    try:
        if not path.exists():
            return
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = BACKUP_DIR / f"{path.parent.name}_{path.stem}_{stamp}{path.suffix}"
        dest.write_bytes(path.read_bytes())
        snaps = sorted(BACKUP_DIR.glob(f"{path.parent.name}_{path.stem}_*{path.suffix}"))
        for old in snaps[:-keep]:
            old.unlink(missing_ok=True)
    except Exception:
        pass

# ── Icon loader ────────────────────────────────────────────────────────────────

_icon_cache: dict = {}

def icon(name: str, tint: str = "ink", size: int = 20):
    key = (name, tint, size)
    if key in _icon_cache:
        return _icon_cache[key]
    p = ICON_DIR / f"{name}_{tint}.png"
    if not p.exists():
        return None
    try:
        im = ctk.CTkImage(Image.open(p), size=(size, size))
    except Exception:
        return None
    _icon_cache[key] = im
    return im

# ── Markdown → HTML (light) ────────────────────────────────────────────────────

def md_to_html(text: str) -> str:
    face = SETTINGS.get("font_face", "Segoe UI")
    size = int(SETTINGS.get("font_size", 16))
    if HAS_RENDER:
        try:
            body = md_lib.markdown(text, extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
        except Exception:
            body = f"<pre style='white-space:pre-wrap'>{text}</pre>"
    else:
        body = f"<pre style='white-space:pre-wrap'>{text}</pre>"

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{background:{BG};color:{INK};font-family:'{face}',Segoe UI,Arial,sans-serif;
     font-size:{size}px;padding:26px 32px;line-height:1.85;}}
h1{{color:{BLUE};font-size:2em;border-bottom:3px solid {YOLK};
   padding-bottom:12px;margin:0 0 22px 0;letter-spacing:-0.5px;}}
h2{{color:{INK};font-size:1.5em;margin:30px 0 10px 0;border-left:4px solid {YOLK};padding-left:12px;}}
h3{{color:{BLUE};font-size:1.22em;margin:22px 0 8px 0;}}
h4{{color:{INK2};font-size:1.05em;margin:16px 0 6px 0;}}
p{{margin:10px 0;}}
code{{background:{YOLK_SOFT};padding:2px 7px;border-radius:4px;
     font-family:Consolas,monospace;font-size:0.88em;color:{YOLK_DK};}}
pre{{background:#FFFDF6;padding:16px;border-radius:10px;border:1px solid {BORDER};
    overflow-x:auto;margin:14px 0;}}
pre code{{background:transparent;padding:0;color:{INK};}}
blockquote{{border-left:4px solid {BLUE};margin:12px 0;padding:8px 18px;color:{INK2};
           background:{BLUE_SOFT};border-radius:0 8px 8px 0;}}
a{{color:{BLUE};text-decoration:none;border-bottom:1px dashed {BLUE};}}
a:hover{{color:{YOLK_DK};border-color:{YOLK};}}
img{{max-width:100%;border-radius:12px;margin:12px 0;display:block;
    box-shadow:0 6px 18px rgba(26,43,74,0.10);}}
hr{{border:none;border-top:2px dotted {BORDER};margin:24px 0;}}
ul,ol{{padding-left:28px;margin:10px 0;}} li{{margin:7px 0;}}
table{{border-collapse:collapse;width:100%;margin:16px 0;border-radius:8px;overflow:hidden;}}
th{{background:{BLUE};color:#fff;padding:11px 15px;text-align:left;}}
td{{padding:9px 15px;border:1px solid {BORDER};}}
tr:nth-child(even){{background:{CARD2};}}
strong{{color:{YOLK_DK};}} em{{color:{BLUE};}}

/* Visually constructive Top Picks styling */
.pick-container {{
    max-width: 900px;
    margin: 0 auto;
}}
.pick-card {{
    background: {CARD};
    border: 1px solid {BORDER};
    border-radius: 12px;
    padding: 24px;
    margin-bottom: 24px;
    box-shadow: 0 4px 12px {SHADOW};
}}
.pick-title {{
    color: {BLUE};
    font-size: 1.45em;
    font-weight: bold;
    margin-bottom: 8px;
    border-bottom: 1px solid {BORDER};
    padding-bottom: 10px;
}}
.pick-meta {{
    font-size: 0.85em;
    color: {DIM};
    margin-bottom: 16px;
}}
.pick-meta-item {{
    display: inline-block;
    margin-right: 18px;
}}
.pick-section {{
    margin-bottom: 12px;
}}
.pick-section-title {{
    font-weight: bold;
    color: {INK2};
    font-size: 0.9em;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
}}
.pick-summary {{
    color: {INK};
    line-height: 1.6;
}}
.pick-why {{
    background: {BLUE_SOFT};
    border-left: 4px solid {BLUE};
    padding: 12px 16px;
    border-radius: 0 8px 8px 0;
    margin: 14px 0;
    color: {INK};
    line-height: 1.6;
}}
.pick-tags {{
    margin-top: 14px;
    border-top: 1px dashed {BORDER};
    padding-top: 12px;
}}
.pick-tag {{
    display: inline-block;
    background: {YOLK_SOFT};
    color: {YOLK_DK};
    font-size: 0.8em;
    font-weight: bold;
    padding: 3px 10px;
    border-radius: 12px;
    border: 1px solid {YOLK};
    margin-right: 6px;
    margin-bottom: 4px;
}}
</style></head><body>{body}</body></html>"""

# ── agy fallback launcher (external) ──────────────────────────────────────────

def clean_env() -> dict:
    """Return a clean OS environment for spawning child processes from a
    PyInstaller-frozen executable.  PyInstaller injects several variables
    that corrupt any child Python or Go process:

      PYTHONPATH / PYTHONHOME  → point to the _MEIPASS temp bundle
      PATH                     → prepended with the _MEIPASS directory
      TCL_LIBRARY / TK_LIBRARY → point to bundled Tk inside _MEIPASS

    We remove / restore all of them so agy.EXE sees a stock system env.
    """
    env = os.environ.copy()
    env["AGY_NO_PLUGINS"] = "1"
    env["AGY_NO_MCP"] = "1"
    env["AGY_NO_TOOLS"] = "1"
    if not getattr(sys, 'frozen', False):
        return env  # running from source, nothing to clean

    meipass = getattr(sys, '_MEIPASS', None)

    # --- Restore or remove PyInstaller-injected Python variables ---
    for var in ('PYTHONPATH', 'PYTHONHOME', 'TCL_LIBRARY', 'TK_LIBRARY'):
        orig_key = f"{var}_original"
        if orig_key in env:
            env[var] = env[orig_key]   # restore what was there before freeze
        else:
            env.pop(var, None)         # it didn't exist before freeze → remove it

    # --- Clean _MEIPASS entries that PyInstaller prepended to PATH ---
    if meipass:
        path_parts = env.get('PATH', '').split(os.pathsep)
        clean_parts = [p for p in path_parts
                       if not p.startswith(meipass) and p != meipass]
        env['PATH'] = os.pathsep.join(clean_parts)

    return env

def _launch_console(exe: str, cwd: str = None):
    """Launch exe in a new console. Prefers Windows Terminal (proper VT/ANSI
    redraw for spinners) over legacy conhost, which garbles carriage-return
    animations like agy's loading spinner."""
    env = clean_env()
    wt = shutil.which("wt")
    if wt:
        subprocess.Popen([wt, "-d", cwd or os.getcwd(), exe], env=env, creationflags=subprocess.CREATE_NEW_CONSOLE)
    else:
        subprocess.Popen(["cmd.exe", "/k", f'"{exe}"'], env=env, cwd=cwd, creationflags=subprocess.CREATE_NEW_CONSOLE)

def launch_agy(prompt_hint: str = ""):
    agy = agy_exe()
    if not agy.exists() and not shutil.which("agy"):
        return
    exe = str(agy) if agy.exists() else "agy"
    _launch_console(exe)

# ── Export ────────────────────────────────────────────────────────────────────

def export_content(ds: str) -> Path:
    lines = [f"# MAYA Export — {pretty_date(ds)}\n\n"]
    tp = path_for("top_picks", ds)
    if tp.exists():
        lines += ["---\n\n# Top Picks\n\n", tp.read_text(encoding="utf-8", errors="replace"), "\n\n"]
    plan = load_json(path_for("plan", ds), {})
    if plan.get("sections"):
        lines.append("---\n\n# Today's Plan\n\n")
        for s in plan["sections"]:
            lines.append(f"## {s.get('name','')}\n\n")
            for t in s.get("tasks", []):
                tick = "x" if t.get("done") else " "
                pr = t.get("priority", "med").upper()
                lines.append(f"- [{tick}] **[{pr}]** {t.get('title','')}\n")
            lines.append("\n")
    act = load_json(path_for("activities", ds), {})
    if act.get("tasks"):
        lines.append("---\n\n# Activities\n\n")
        for t in act["tasks"]:
            note = f" — {t['note']}" if t.get("note") else ""
            lines.append(f"- [{t.get('status','active')}] {t.get('title','')}{note}\n")
        lines.append("\n")
    les = load_json(path_for("lessons", ds), {})
    if les.get("lessons"):
        lines.append("---\n\n# Lessons\n\n")
        for i, l in enumerate(les["lessons"], 1):
            mark = "✓" if l.get("learned") else "○"
            lines.append(f"### {i}. {mark} {l.get('title','')}\n\n")
            if l.get("what"):
                lines.append(f"{l['what']}\n\n")
            if l.get("action"):
                lines.append(f"> **Action:** {l['action']}\n\n")
    out = date_dir(ds) / "MAYA_export.md"
    out.write_text("".join(lines), encoding="utf-8")
    return out


# ── Modern button factory ──────────────────────────────────────────────────────

def pill_button(parent, text, command, kind="primary", icon_name=None, icon_tint=None, width=None, height=None):
    styles = {
        "primary": (BLUE, BLUE_DK, "#FFFFFF"),
        "accent":  (YOLK, YOLK_DK, INK),
        "ghost":   (CARD, BG2, INK),
        "danger":  (RED_SOFT, RED, RED),
    }
    fg, hov, txt = styles.get(kind, styles["primary"])
    img = icon(icon_name, icon_tint or ("cream" if kind == "primary" else "ink"), 18) if icon_name else None
    kw = dict(
        text=("  " + text) if (text and img) else text,
        command=command, fg_color=fg, hover_color=hov, text_color=txt,
        font=(FONT_BODY, 13, "bold"), height=height or 38, corner_radius=10,
        border_width=(1 if kind == "ghost" else 0), border_color=BORDER,
        image=img, compound="left",
    )
    if width:
        kw["width"] = width
    return ctk.CTkButton(parent, **kw)

# ── Card frame ─────────────────────────────────────────────────────────────────

def card_frame(parent, **kw):
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=14,
                        border_width=1, border_color=BORDER, **kw)

# ── Instruction editor ────────────────────────────────────────────────────────

def open_instr_editor(master, key: str, tab_name: str):
    dlg = ctk.CTkToplevel(master)
    dlg.title(f"{tab_name} — AI Instruction")
    dlg.configure(fg_color=BG)
    dlg.geometry("660x400")
    dlg.resizable(True, True)
    dlg.transient(master)
    dlg.grid_columnconfigure(0, weight=1)
    dlg.grid_rowconfigure(2, weight=1)

    ctk.CTkLabel(dlg, text=f"{tab_name} instruction", font=(FONT_HEAD, 18, "bold"),
                 text_color=INK).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 2))
    ctk.CTkLabel(dlg, text="Sent to agy when you click the Generate button on this tab.",
                 font=(FONT_BODY, 12), text_color=DIM).grid(row=1, column=0, sticky="w",
                 padx=20, pady=(0, 10))

    box = ctk.CTkTextbox(dlg, wrap="word", font=(FONT_BODY, 13),
                         fg_color=CARD, text_color=INK, border_color=BORDER,
                         border_width=1, corner_radius=10)
    box.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 8))
    box.insert("1.0", SETTINGS.get(key, ""))

    btns = ctk.CTkFrame(dlg, fg_color="transparent")
    btns.grid(row=3, column=0, sticky="e", padx=20, pady=(4, 16))

    def _save():
        save_settings({**SETTINGS, key: box.get("1.0", "end").strip()})
        if APP: APP.toast(f"{tab_name} instruction saved", "ok")
        dlg.destroy()

    pill_button(btns, "Cancel", dlg.destroy, "ghost", "x", "ink", width=100).pack(side="left", padx=6)
    pill_button(btns, "Save", _save, "accent", "check", "ink", width=110).pack(side="left", padx=6)
    dlg.after(60, lambda: (dlg.grab_set(), dlg.lift(), dlg.focus_force()))


# ── Inline edit dialog ─────────────────────────────────────────────────────────

class EditDialog(ctk.CTkToplevel):
    """Generic modal editor. fields: list of (key, label, kind, options).
    kind in {'entry','text','option'}. Calls on_ok(values_dict)."""
    def __init__(self, master, heading, fields, values, on_ok):
        super().__init__(master)
        self._fields = fields
        self._on_ok = on_ok
        self._widgets = {}
        self.title(heading)
        self.configure(fg_color=BG)
        self.geometry("520x%d" % (150 + 78 * len(fields)))
        self.resizable(False, False)
        self.transient(master)
        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=heading, font=(FONT_HEAD, 18, "bold"),
                     text_color=INK).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 8))

        r = 1
        for key, label, kind, options in fields:
            ctk.CTkLabel(self, text=label, font=(FONT_BODY, 13, "bold"),
                         text_color=INK2).grid(row=r, column=0, sticky="w", padx=20, pady=(8, 2)); r += 1
            val = values.get(key, "")
            if kind == "entry":
                w = ctk.CTkEntry(self, height=38, font=(FONT_BODY, 13), fg_color=CARD,
                                 border_color=BORDER, text_color=INK, corner_radius=8)
                w.insert(0, str(val))
            elif kind == "text":
                w = ctk.CTkTextbox(self, height=80, font=(FONT_BODY, 13), fg_color=CARD,
                                   border_color=BORDER, border_width=1, text_color=INK, corner_radius=8)
                w.insert("1.0", str(val))
            else:  # option
                w = ctk.CTkOptionMenu(self, values=options, font=(FONT_BODY, 13),
                                      fg_color=BLUE_SOFT, button_color=BLUE, button_hover_color=BLUE_DK,
                                      text_color=INK, dropdown_fg_color=CARD, dropdown_text_color=INK)
                w.set(val if val in options else options[0])
            w.grid(row=r, column=0, sticky="ew", padx=20, pady=(0, 4)); r += 1
            self._widgets[key] = (w, kind)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=r, column=0, sticky="e", padx=20, pady=16)
        pill_button(btns, "Cancel", self.destroy, "ghost", "x", "ink", width=100).pack(side="left", padx=6)
        pill_button(btns, "Save", self._save, "accent", "check", "ink", width=110).pack(side="left", padx=6)

        self.after(60, self._grab)

    def _grab(self):
        try:
            self.grab_set(); self.lift(); self.focus_force()
        except Exception:
            pass

    def _save(self):
        out = {}
        for key, (w, kind) in self._widgets.items():
            out[key] = w.get("1.0", "end").strip() if kind == "text" else w.get()
        self.destroy()
        self._on_ok(out)


class GeneratingPopup(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("Generating")
        self.configure(fg_color=BG)
        self.geometry("380x180")
        self.resizable(False, False)
        self.transient(master)
        
        # Center the window relative to master
        self.update_idletasks()
        if master:
            x = master.winfo_rootx() + (master.winfo_width() - 380) // 2
            y = master.winfo_rooty() + (master.winfo_height() - 180) // 2
            self.geometry(f"380x180+{max(0, x)}+{max(0, y)}")
        
        self.grid_columnconfigure(0, weight=1)
        
        ctk.CTkLabel(self, text="Generating with agy...", font=(FONT_HEAD, 16, "bold"),
                     text_color=INK).grid(row=0, column=0, pady=(20, 4))
        
        # Progress bar (loading effect)
        self._progress = ctk.CTkProgressBar(self, height=8, corner_radius=4,
                                            fg_color=BG2, progress_color=BLUE)
        self._progress.grid(row=1, column=0, sticky="ew", padx=30, pady=8)
        self._progress.configure(mode="indeterminate")
        self._progress.start()
        
        ctk.CTkLabel(self, text="This might take a minute, please wait...",
                     font=(FONT_BODY, 11), text_color=DIM).grid(row=2, column=0, pady=(0, 10))
        
        # Cancel button to close manually
        pill_button(self, "Cancel", self.destroy, "ghost", "x", "ink", width=90).grid(row=3, column=0, pady=(4, 16))
        
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.after(60, self._grab)

    def _grab(self):
        try:
            self.grab_set(); self.lift(); self.focus_force()
        except Exception:
            pass


def move_in_list(lst, item, delta):
    """Move item within lst by delta (-1 up / +1 down). Returns True if moved."""
    try:
        i = lst.index(item)
    except ValueError:
        return False
    j = i + delta
    if 0 <= j < len(lst):
        lst[i], lst[j] = lst[j], lst[i]
        return True
    return False


def reorder_buttons(parent, on_up, on_down):
    """Stacked up/down chevrons in a thin column."""
    col = ctk.CTkFrame(parent, fg_color="transparent")
    ctk.CTkButton(col, text="▲", width=26, height=20, corner_radius=6,
                  font=(FONT_BODY, 10), fg_color="transparent", hover_color=BG2,
                  text_color=DIM, command=on_up).pack(pady=(0, 1))
    ctk.CTkButton(col, text="▼", width=26, height=20, corner_radius=6,
                  font=(FONT_BODY, 10), fg_color="transparent", hover_color=BG2,
                  text_color=DIM, command=on_down).pack()
    return col

# ── Tab header ─────────────────────────────────────────────────────────────────

class TabHeader(ctk.CTkFrame):
    def __init__(self, parent, title, subtitle, icon_name):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkFrame(self, fg_color=BLUE_SOFT, corner_radius=14, width=58, height=58)
        badge.grid(row=0, column=0, rowspan=2, padx=(2, 14), pady=4)
        badge.grid_propagate(False)
        ic = icon(icon_name, "blue", 30)
        ctk.CTkLabel(badge, text="" if ic else "•", image=ic).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(self, text=title, font=(FONT_HEAD, 26, "bold"),
                     text_color=INK, anchor="w").grid(row=0, column=1, sticky="sw", pady=(6, 0))
        ctk.CTkLabel(self, text=subtitle, font=(FONT_BODY, 13),
                     text_color=DIM, anchor="w").grid(row=1, column=1, sticky="nw", pady=(0, 6))

        self.actions = ctk.CTkFrame(self, fg_color="transparent")
        self.actions.grid(row=0, column=2, rowspan=2, sticky="e", padx=2)

# ── Stat chip ──────────────────────────────────────────────────────────────────

class StatChip(ctk.CTkFrame):
    def __init__(self, parent, label, value, color=BLUE, tint=BLUE_SOFT, icon_name=None):
        super().__init__(parent, fg_color=tint, corner_radius=12, border_width=0)
        self.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 0))
        ic = icon(icon_name, "blue" if color == BLUE else
                  "green" if color == GREEN else
                  "yolk" if color == YOLK_DK else
                  "red" if color == RED else "dim", 16) if icon_name else None
        if ic:
            ctk.CTkLabel(top, text="", image=ic).grid(row=0, column=0, padx=(0, 6))
        self._val = ctk.CTkLabel(top, text=str(value), font=(FONT_HEAD, 24, "bold"), text_color=color)
        self._val.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(self, text=label, font=(FONT_BODY, 11, "bold"),
                     text_color=INK2, anchor="w").grid(row=1, column=0, sticky="w", padx=14, pady=(0, 12))

    def set(self, value):
        self._val.configure(text=str(value))

# ── Top Picks (markdown watch) ─────────────────────────────────────────────────

class TopPicksTab(ctk.CTkFrame):
    POLL_MS = 800

    def __init__(self, parent, ask_agy_fn=None):
        super().__init__(parent, fg_color="transparent")
        self._ask_agy_fn = ask_agy_fn
        self._last_mtime = -1.0
        self._raw = ""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = TabHeader(self, "Top Picks Today", f"Hot AI & tech for {TODAY}", "top_picks")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        self._btn_ask = pill_button(hdr.actions, "Refresh with agy", self._ask, "accent",
                    "sparkles", "ink")
        self._btn_ask.grid(row=0, column=0, padx=4)
        pill_button(hdr.actions, "Edit instruction", self._edit_instr, "ghost",
                    "edit", "ink").grid(row=0, column=1, padx=4)

        if HAS_RENDER:
            self._html = HtmlFrame(self, messages_enabled=False, vertical_scrollbar=True)
            self._html.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))
            self._html.load_html(self._empty_html())
        else:
            self._html = None
            self._box = ctk.CTkTextbox(self, font=("Consolas", 15), fg_color=CARD, text_color=INK)
            self._box.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))

        self._poll()

    def _empty_html(self):
        return md_to_html(
            f"# Welcome to Maya Developer Workspace! 👋\n\n"
            f"This dashboard helps you coordinate your daily developer schedule, plan projects, track lessons, and generate professional blog posts.\n\n"
            f"### 🚀 How to Get Started:\n"
            f"1. **Set up your AI Executable**: Go to the **Settings** tab and click the **Auto-Detect** button next to 'agy executable path' to automatically locate the `agy` binary on your PC, or paste the path manually.\n"
            f"2. **Fetch Today's Tech News**: Click the **Refresh with agy** button above to launch an automated research task. Once completed, this home screen will automatically update with today's hot picks!\n"
            f"3. **Plan & Log**: Use the **Activities**, **Plan**, and **Lessons** tabs to manage your daily developer tasks, notes, and checklist items.\n"
            f"4. **AI Research & Writing (Step 1-5)**: Navigate to the **Research** tab to research practitioner discussions, outline articles, draft SEO-optimized posts, run audits, generate cover banners, and sync your finished articles to WordPress, Ghost CMS, or local Git repositories.\n"
        )

    def _empty_txt(self):
        return (
            f"Welcome to Maya Developer Workspace! \n\n"
            f"This dashboard helps you coordinate your daily developer schedule, plan projects, track lessons, and generate professional blog posts.\n\n"
            f"How to Get Started:\n"
            f"1. Set up your AI Executable: Go to the Settings tab and click the 'Auto-Detect' button next to 'agy executable path' to automatically locate the 'agy' binary on your PC.\n"
            f"2. Fetch Today's Tech News: Click the 'Refresh with agy' button above to launch an automated research task.\n"
            f"3. Plan & Log: Use the Activities, Plan, and Lessons tabs to manage your daily developer tasks, notes, and checklist items.\n"
            f"4. AI Research & Writing: Navigate to the Research tab to research, outline, draft, verify, generate banners, and publish drafts.\n"
        )

    @property
    def path(self) -> Path:
        return path_for("top_picks", APP.current_date if APP else today_str())

    def _ask(self):
        instr = SETTINGS.get("top_picks_instruction", "")
        ds = APP.current_date if APP else today_str()
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(build_prompt(instr, "top_picks", ds))
        else:
            launch_agy()

    def _edit_instr(self):
        open_instr_editor(self.winfo_toplevel(), "top_picks_instruction", "Top Picks")

    def on_date_change(self):
        self._last_mtime = -2.0
        self._raw = ""
        self.rerender()

    def _poll(self):
        try:
            p = self.path
            if p.exists():
                m = p.stat().st_mtime
                if m != self._last_mtime:
                    self._last_mtime = m
                    self._raw = p.read_text(encoding="utf-8", errors="replace")
                    self.rerender()
            elif self._last_mtime != -2.0:
                self._last_mtime = -2.0
                self._raw = ""
                self.rerender()
        except Exception:
            pass
        self.after(self.POLL_MS, self._poll)

    def rerender(self):
        if hasattr(self, "_loading_popup") and self._loading_popup:
            try:
                self._loading_popup.destroy()
            except Exception:
                pass
            self._loading_popup = None
            
        if self._html:
            self._html.load_html(md_to_html(self._raw) if self._raw.strip() else self._empty_html())
        else:
            self._box.delete("1.0", "end")
            self._box.insert("1.0", self._raw or self._empty_txt())


# ── Research Tab (Collaborative AI Research & Writing) ─────────────────────────

def slugify(text: str) -> str:
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    return text or "untitled-blog"


class ResearchTab(ctk.CTkFrame):
    POLL_MS = 1500

    def __init__(self, parent, ask_agy_fn=None):
        super().__init__(parent, fg_color="transparent")
        self._ask_agy_fn = ask_agy_fn
        self._active_view = "discourse"
        self._last_mtimes = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self._poll()

    def research_path(self, kind: str) -> Path:
        ds = APP.current_date if APP else today_str()
        topic = self._topic_entry.get().strip()
        slug = slugify(topic) if topic else "current-research"
        folder = CONTENT_DIR / ds / slug
        folder.mkdir(parents=True, exist_ok=True)
        
        if kind == "brand":
            return BASE_DIR / "BRAND.md"
        elif kind == "voice":
            return BASE_DIR / "VOICE.md"
        elif kind == "image_prompts":
            return folder / "image_prompts.json"
        elif kind == "discourse":
            return folder / "discourse.md"
        elif kind == "outline":
            return folder / "outline.md"
        elif kind == "draft":
            return folder / "draft.md"
        elif kind == "draft_bak":
            return folder / "draft.md.bak"
        elif kind == "review":
            return folder / "review.md"
        elif kind == "socials":
            return folder / "socials.md"
        else:
            return folder / f"{kind}.md"

    def _build(self):
        hdr = TabHeader(self, "Research & Writing", "Collaborative AI Research Assistant · Outlines · Drafting · QA", "research")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        
        # Split body: Left (Controls), Right (Viewer)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 18))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=0) # controls width is fixed
        body.grid_columnconfigure(1, weight=1) # viewer expands

        # Left panel: Controls (335px width)
        left = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=14,
                                      border_width=1, border_color=BORDER, width=335)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        left.grid_columnconfigure(0, weight=1)

        # Section 1: Job Briefing (Tier 2)
        ctk.CTkLabel(left, text="1. JOB BRIEFING (TIER 2)", font=(FONT_BODY, 11, "bold"),
                     text_color=BLUE).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        ctk.CTkLabel(left, text="Primary Topic / Keyword", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=1, column=0, sticky="w", padx=14, pady=(6, 2))
        self._topic_entry = ctk.CTkEntry(left, placeholder_text="e.g. Enterprise Agentic AI in 2026",
                                         fg_color=BG, border_color=BORDER, text_color=INK, height=36)
        self._topic_entry.grid(row=2, column=0, sticky="ew", padx=14, pady=2)

        ctk.CTkLabel(left, text="Search Focus / Custom Angle", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=3, column=0, sticky="w", padx=14, pady=(6, 2))
        self._focus_entry = ctk.CTkEntry(left, placeholder_text="e.g. Focus on telecom & productivity",
                                         fg_color=BG, border_color=BORDER, text_color=INK, height=36)
        self._focus_entry.grid(row=4, column=0, sticky="ew", padx=14, pady=2)

        ctk.CTkLabel(left, text="Content Template", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=5, column=0, sticky="w", padx=14, pady=(6, 2))
        self._template_menu = ctk.CTkOptionMenu(left, values=[
            "how-to-guide", "listicle", "case-study", "comparison", "pillar-page", "thought-leadership", "tutorial", "news-analysis"
        ], fg_color=BG2, button_color=BLUE, button_hover_color=BLUE_DK, text_color=INK, height=36)
        self._template_menu.grid(row=6, column=0, sticky="ew", padx=14, pady=2)

        ctk.CTkFrame(left, fg_color=BORDER, height=1).grid(row=7, column=0, sticky="ew", padx=14, pady=16)

        # Section 2: Step-by-Step Execution & Feedback (Tier 3)
        ctk.CTkLabel(left, text="2. SEQUENTIAL WORKFLOW (TIER 3)", font=(FONT_BODY, 11, "bold"),
                     text_color=BLUE).grid(row=8, column=0, sticky="w", padx=14, pady=(0, 6))

        # --- STEP 1: Research Discourse ---
        ctk.CTkLabel(left, text="Step 1: Discourse Research", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=9, column=0, sticky="w", padx=14, pady=(8, 2))
        self._instr_discourse = ctk.CTkEntry(left, placeholder_text="Feedback / sites / update directives...",
                                             fg_color=BG, border_color=BORDER, text_color=INK, height=30)
        self._instr_discourse.grid(row=10, column=0, sticky="ew", padx=14, pady=2)
        
        r1 = ctk.CTkFrame(left, fg_color="transparent")
        r1.grid(row=11, column=0, sticky="ew", padx=14, pady=(2, 8))
        r1.grid_columnconfigure(0, weight=1)
        pill_button(r1, "Run/Update Research", self._run_discourse, "accent", "sparkles", "ink", height=30).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._status_discourse = ctk.CTkLabel(r1, text="● Idle", font=(FONT_BODY, 11, "bold"), text_color=DIM)
        self._status_discourse.grid(row=0, column=1)

        # --- STEP 2: Generate Outline ---
        ctk.CTkLabel(left, text="Step 2: Content Outline", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=12, column=0, sticky="w", padx=14, pady=(8, 2))
        self._instr_outline = ctk.CTkEntry(left, placeholder_text="Outline tweaks / new sections...",
                                           fg_color=BG, border_color=BORDER, text_color=INK, height=30)
        self._instr_outline.grid(row=13, column=0, sticky="ew", padx=14, pady=2)

        r2 = ctk.CTkFrame(left, fg_color="transparent")
        r2.grid(row=14, column=0, sticky="ew", padx=14, pady=(2, 8))
        r2.grid_columnconfigure(0, weight=1)
        pill_button(r2, "Generate/Update Outline", self._run_outline, "accent", "edit", "ink", height=30).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._status_outline = ctk.CTkLabel(r2, text="● Idle", font=(FONT_BODY, 11, "bold"), text_color=DIM)
        self._status_outline.grid(row=0, column=1)

        # --- STEP 3: Write Draft ---
        ctk.CTkLabel(left, text="Step 3: Write Draft", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=15, column=0, sticky="w", padx=14, pady=(8, 2))
        self._instr_draft = ctk.CTkEntry(left, placeholder_text="Tone edits / intro hooks / expansions...",
                                         fg_color=BG, border_color=BORDER, text_color=INK, height=30)
        self._instr_draft.grid(row=16, column=0, sticky="ew", padx=14, pady=2)

        r3 = ctk.CTkFrame(left, fg_color="transparent")
        r3.grid(row=17, column=0, sticky="ew", padx=14, pady=(2, 8))
        r3.grid_columnconfigure(0, weight=1)
        pill_button(r3, "Write/Update Draft", self._run_draft, "primary", "send", "cream", height=30).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._status_draft = ctk.CTkLabel(r3, text="● Idle", font=(FONT_BODY, 11, "bold"), text_color=DIM)
        self._status_draft.grid(row=0, column=1)

        # --- STEP 4: Factcheck & QA ---
        ctk.CTkLabel(left, text="Step 4: Factcheck & QA", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=18, column=0, sticky="w", padx=14, pady=(8, 2))
        self._instr_review = ctk.CTkEntry(left, placeholder_text="Focus specific stats / SEO keywords...",
                                          fg_color=BG, border_color=BORDER, text_color=INK, height=30)
        self._instr_review.grid(row=19, column=0, sticky="ew", padx=14, pady=2)

        r4 = ctk.CTkFrame(left, fg_color="transparent")
        r4.grid(row=20, column=0, sticky="ew", padx=14, pady=(2, 16))
        r4.grid_columnconfigure(0, weight=1)
        pill_button(r4, "Verify Facts & SEO", self._run_qa, "accent", "search", "ink", height=30).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._status_review = ctk.CTkLabel(r4, text="● Idle", font=(FONT_BODY, 11, "bold"), text_color=DIM)
        self._status_review.grid(row=0, column=1)

        # Section 3: Images & Graphics (Tier 3)
        ctk.CTkFrame(left, fg_color=BORDER, height=1).grid(row=21, column=0, sticky="ew", padx=14, pady=16)
        
        ctk.CTkLabel(left, text="3. IMAGES & GRAPHICS", font=(FONT_BODY, 11, "bold"),
                     text_color=BLUE).grid(row=22, column=0, sticky="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(left, text="Select AI Image Prompt", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=23, column=0, sticky="w", padx=14, pady=(4, 2))
        self._img_prompts_menu = ctk.CTkOptionMenu(left, values=["No prompts generated yet"],
                                                   fg_color=BG2, button_color=BLUE, button_hover_color=BLUE_DK,
                                                   text_color=INK, height=36)
        self._img_prompts_menu.grid(row=24, column=0, sticky="ew", padx=14, pady=2)

        pill_button(left, "Generate Selected Image", self._run_image, "accent", "sparkles", "ink", height=32).grid(
            row=25, column=0, sticky="ew", padx=14, pady=(6, 4)
        )
        
        pill_button(left, "Generate Branded OG Banner", self._run_og_banner, "accent", "image", "ink", height=32).grid(
            row=26, column=0, sticky="ew", padx=14, pady=(2, 4)
        )

        pill_button(left, "Upload Custom Image", self._upload_image, "ghost", "plus", "ink", height=32).grid(
            row=27, column=0, sticky="ew", padx=14, pady=(2, 16)
        )

        # Section 4: Publishing & Distribution (Step 5)
        ctk.CTkFrame(left, fg_color=BORDER, height=1).grid(row=28, column=0, sticky="ew", padx=14, pady=16)

        ctk.CTkLabel(left, text="4. PUBLISH & REPURPOSE", font=(FONT_BODY, 11, "bold"),
                     text_color=BLUE).grid(row=29, column=0, sticky="w", padx=14, pady=(0, 6))

        ctk.CTkLabel(left, text="Select CMS / Git Target", font=(FONT_BODY, 12, "bold"),
                     text_color=INK).grid(row=30, column=0, sticky="w", padx=14, pady=(4, 2))
        self._publish_platform_menu = ctk.CTkOptionMenu(left, values=[
            "WordPress REST API", "Ghost CMS API", "GitHub / Git Repo"
        ], fg_color=BG2, button_color=BLUE, button_hover_color=BLUE_DK, text_color=INK, height=36)
        self._publish_platform_menu.grid(row=31, column=0, sticky="ew", padx=14, pady=2)

        pill_button(left, "Sync & Publish Article", self._publish_article, "primary", "check", "cream", height=34).grid(
            row=32, column=0, sticky="ew", padx=14, pady=(8, 4)
        )

        pill_button(left, "Repurpose for Socials", self._repurpose_socials, "accent", "send", "ink", height=34).grid(
            row=33, column=0, sticky="ew", padx=14, pady=(2, 16)
        )

        # Right panel: Viewer (Expands)
        right = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14, border_width=1, border_color=BORDER)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        # Viewer toggle buttons header
        v_hdr = ctk.CTkFrame(right, fg_color="transparent")
        v_hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=10)
        
        self._view_btns = {}
        views = [
            ("discourse", "1. Research"), ("outline", "2. Outline"), ("draft", "3. Draft"), 
            ("review", "4. QA Report"), ("socials", "Socials"), ("diff", "Visual Diff"), 
            ("gallery", "Media Gallery"), ("brand", "Brand Guide")
        ]
        for idx, (vk, vlbl) in enumerate(views):
            v_hdr.grid_columnconfigure(idx, weight=1)
            b = ctk.CTkButton(v_hdr, text=vlbl, font=(FONT_BODY, 12, "bold"), corner_radius=8,
                               fg_color="transparent", text_color=INK2, hover_color=BG2, height=32,
                               command=lambda k=vk: self._switch_view(k))
            b.grid(row=0, column=idx, padx=2, sticky="ew")
            self._view_btns[vk] = b

        # Edit and Open buttons row
        act_row = ctk.CTkFrame(right, fg_color="transparent")
        act_row.grid(row=0, column=1, padx=(10, 16))
        self._edit_btn = pill_button(act_row, "Edit file", self._edit_current_file, "ghost", "edit", "ink", height=30)
        self._edit_btn.grid(row=0, column=0, padx=4)

        # Viewer container
        if HAS_RENDER:
            self._viewer = HtmlFrame(right, messages_enabled=False, vertical_scrollbar=True)
            self._viewer.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 16))
        else:
            self._viewer = None
            self._viewer_box = ctk.CTkTextbox(right, font=("Consolas", 14), fg_color=CARD2, text_color=INK)
            self._viewer_box.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=16, pady=(0, 16))

        self._switch_view("discourse")

    @property
    def path(self) -> Path:
        if self._active_view == "brand":
            return BASE_DIR / "BRAND.md"
        return self.research_path(self._active_view)

    def _switch_view(self, key):
        self._active_view = key
        for vk, b in self._view_btns.items():
            active = (vk == key)
            b.configure(fg_color=BLUE if active else "transparent",
                        text_color="#FFFFFF" if active else INK2,
                        hover_color=BLUE_DK if active else BG2)
        self.rerender()

    def _edit_current_file(self):
        p = self.path
        if not p.exists():
            APP.toast(f"File {p.name} does not exist yet!", "error")
            return
            
        try:
            if os.name == 'nt':
                os.startfile(str(p))
            else:
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(p)])
            APP.toast(f"Opening {p.name} in external editor", "ok")
        except Exception as e:
            APP.toast(f"Failed to open editor: {e}", "error")

    def _get_images_html(self) -> str:
        ds = APP.current_date if APP else today_str()
        topic = self._topic_entry.get().strip()
        slug = slugify(topic)
        img_dir = CONTENT_DIR / ds / slug / "images"
        
        html = "<h2>Blog Media Gallery</h2>"
        html += "<p style='margin-bottom:20px; color:#555;'>These images are available for your blog post. Reference them in your draft using <code>![Caption](images/filename.png)</code>.</p>"
        
        if not img_dir.exists():
            html += "<p>No images uploaded or generated yet.</p>"
            return html
            
        files = list(img_dir.glob("*.*"))
        if not files:
            html += "<p>No images uploaded or generated yet.</p>"
            return html
            
        html += "<div style='display:inline-block; width:100%;'>"
        for f in files:
            f_uri = f.as_uri()
            rel_path = f"images/{f.name}"
            html += f"""
            <div style='background:#ffffff; border:1px solid #e6dcc2; border-radius:10px; padding:12px; margin:10px; width:260px; float:left; box-shadow:0 2px 8px rgba(0,0,0,0.05);'>
                <img src='{f_uri}' style='width:100%; max-height:160px; object-fit:contain; border-radius:6px; background:#f9f9f9;'>
                <div style='font-size:0.85em; font-family:monospace; margin-top:8px; word-break:break-all; color:#1A2B4A;'>{rel_path}</div>
            </div>
            """
        html += "</div>"
        return html

    def rerender(self):
        content = ""
        if self._active_view == "brand":
            p = BASE_DIR / "BRAND.md"
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
            else:
                content = "# BRAND.md missing\n\nRun `/blog brand init` in the terminal to initialize brand settings."
        elif self._active_view == "gallery":
            if self._viewer:
                self._viewer.load_html(self._get_images_html())
            else:
                ds = APP.current_date if APP else today_str()
                topic = self._topic_entry.get().strip()
                slug = slugify(topic)
                img_dir = CONTENT_DIR / ds / slug / "images"
                if img_dir.exists():
                    files = [f"images/{im.name}" for im in img_dir.glob("*.*")]
                    content = "# Blog Media Gallery\n\n" + "\n".join(files) if files else "No images yet."
                else:
                    content = "# Blog Media Gallery\n\nNo images yet."
                self._viewer_box.delete("1.0", "end")
                self._viewer_box.insert("1.0", content)
            return
        elif self._active_view == "diff":
            if self._viewer:
                self._viewer.load_html(self._get_diff_html())
            else:
                self._viewer_box.delete("1.0", "end")
                self._viewer_box.insert("1.0", "Visual Diff only supported in HTML rendering mode.")
            return
        else:
            p = self.research_path(self._active_view)
            if p.exists():
                content = p.read_text(encoding="utf-8", errors="replace")
            else:
                content = f"# File {p.name} does not exist yet.\n\nRun the corresponding workflow action button on the left to start processing."

        if self._viewer:
            self._viewer.load_html(md_to_html(content) if content.strip() else "<body></body>")
        else:
            self._viewer_box.delete("1.0", "end")
            self._viewer_box.insert("1.0", content)

    def on_date_change(self):
        self._last_mtimes = {}
        self.rerender()

    def _poll(self):
        try:
            ds = APP.current_date if APP else today_str()
            topic = self._topic_entry.get().strip()
            slug = slugify(topic)
            folder = CONTENT_DIR / ds / slug
            
            # Poll status of files
            files = ["discourse", "outline", "draft", "review", "socials"]
            labels = {
                "discourse": self._status_discourse,
                "outline": self._status_outline,
                "draft": self._status_draft,
                "review": self._status_review,
                "socials": None
            }
            
            for k in files:
                p = folder / f"{k}.md"
                lbl = labels.get(k)
                if p.exists():
                    m = p.stat().st_mtime
                    if self._last_mtimes.get(k) != m:
                        self._last_mtimes[k] = m
                        self._dismiss_loading()
                        if k == self._active_view:
                            self.rerender()
                    if lbl:
                        lbl.configure(text="● Ready", text_color=GREEN)
                else:
                    self._last_mtimes[k] = None
                    if lbl:
                        lbl.configure(text="● Idle", text_color=DIM)
                    
            # Poll image prompts JSON
            prompt_file = folder / "image_prompts.json"
            if prompt_file.exists():
                m = prompt_file.stat().st_mtime
                if self._last_mtimes.get("image_prompts") != m:
                    self._last_mtimes["image_prompts"] = m
                    self._dismiss_loading()
                    self._load_image_prompts(prompt_file)
            else:
                self._last_mtimes["image_prompts"] = None
                self._img_prompts_menu.configure(values=["No prompts generated yet"])
                self._img_prompts_menu.set("No prompts generated yet")
                
            # Poll gallery contents
            if self._active_view == "gallery":
                img_dir = folder / "images"
                if img_dir.exists():
                    files = list(img_dir.glob("*.*"))
                    state = (len(files), sum(f.stat().st_mtime for f in files))
                    if self._last_mtimes.get("gallery") != state:
                        self._last_mtimes["gallery"] = state
                        self._dismiss_loading()
                        self.rerender()

            # Poll diff view
            if self._active_view == "diff":
                p_draft = folder / "draft.md"
                p_bak = folder / "draft.md.bak"
                if p_draft.exists() and p_bak.exists():
                    state = (p_draft.stat().st_mtime, p_bak.stat().st_mtime)
                    if self._last_mtimes.get("diff") != state:
                        self._last_mtimes["diff"] = state
                        self._dismiss_loading()
                        self.rerender()
        except Exception:
            pass
        self.after(self.POLL_MS, self._poll)

    def _load_image_prompts(self, path: Path):
        try:
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list) and len(data) > 0:
                prompts = []
                for p in data:
                    prompt_str = p.get("prompt", "")
                    if prompt_str:
                        prompts.append(prompt_str)
                if prompts:
                    self._img_prompts_menu.configure(values=prompts)
                    self._img_prompts_menu.set(prompts[0])
                    return
        except Exception:
            pass
        self._img_prompts_menu.configure(values=["No prompts generated yet"])
        self._img_prompts_menu.set("No prompts generated yet")

    def _dismiss_loading(self):
        if hasattr(self, "_loading_popup") and self._loading_popup:
            try:
                self._loading_popup.destroy()
            except Exception:
                pass
            self._loading_popup = None

    def _upload_image(self):
        from tkinter import filedialog
        import shutil
        
        topic = self._topic_entry.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required to establish the blog folder!", "error")
            return
            
        ds = APP.current_date if APP else today_str()
        slug = slugify(topic)
        img_dir = CONTENT_DIR / ds / slug / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        path = filedialog.askopenfilename(
            title="Select Image File",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.gif")]
        )
        if not path:
            return
            
        src_path = Path(path)
        dest_path = img_dir / f"uploaded_{src_path.name}"
        try:
            shutil.copy(src_path, dest_path)
            APP.toast(f"Uploaded {src_path.name} successfully!", "ok")
            self.rerender()
        except Exception as e:
            APP.toast(f"Upload failed: {e}", "error")

    def _run_image(self):
        topic = self._topic_entry.get().strip()
        prompt_text = self._img_prompts_menu.get()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
        if not prompt_text or prompt_text == "No prompts generated yet":
            APP.toast("Please generate draft and select an image prompt first!", "error")
            return
            
        ds = APP.current_date if APP else today_str()
        slug = slugify(topic)
        img_dir = CONTENT_DIR / ds / slug / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        
        num_existing = len(list(img_dir.glob("generated_*.png")))
        dest_filename = f"generated_{num_existing + 1}.png"
        dest_file = img_dir / dest_filename
        
        command = f"/blog image generate \"{prompt_text}\""
        prompt = f"{command}\n\nTARGET FILE (write here, overwrite it): {dest_file}"
        
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)

    def _get_diff_html(self) -> str:
        import difflib
        draft = self.research_path("draft")
        bak = self.research_path("draft_bak")
        
        if not draft.exists() or not bak.exists():
            return "<h2>Visual Diff</h2><p style='color: #666;'>You must update the draft at least once to see a revision diff.</p>"
            
        try:
            before_text = bak.read_text(encoding="utf-8", errors="replace")
            after_text = draft.read_text(encoding="utf-8", errors="replace")
            
            fromlines = before_text.splitlines()
            tolines = after_text.splitlines()
            diff_obj = difflib.HtmlDiff()
            table_html = diff_obj.make_table(fromlines, tolines, context=True, numlines=3)
            
            html = f"""
            <html>
            <head>
            <style>
                body {{ font-family: sans-serif; background: #faf8f5; color: #1a1a1a; padding: 20px; }}
                table.diff {{ font-family: monospace; border-collapse: collapse; width: 100%; border: 1px solid #ccc; font-size: 13px; }}
                th.diff_header {{ background: #eee; border: 1px solid #ccc; padding: 4px; text-align: right; width: 40px; }}
                td.diff_header {{ background: #f5f5f5; border: 1px solid #ccc; padding: 4px; text-align: right; color: #999; }}
                td.diff_next {{ background: #f0f0f0; border: 1px solid #ccc; display: none; }}
                td.diff_add {{ background: #e6ffed; }}
                td.diff_chg {{ background: #fffdef; }}
                td.diff_sub {{ background: #ffeef0; }}
                span.diff_add {{ background: #acf2bd; text-decoration: none; }}
                span.diff_chg {{ background: #f8e3a1; text-decoration: none; }}
                span.diff_sub {{ background: #fdb8c0; text-decoration: none; }}
                .diff_empty {{ background: #fff; }}
            </style>
            </head>
            <body>
                <h2>Draft Revisions Compare</h2>
                <p style='color: #666; font-size: 0.9em; margin-bottom: 20px;'>Showing diff of the draft before and after the last update.</p>
                {table_html}
            </body>
            </html>
            """
            return html
        except Exception as e:
            return f"<h2>Visual Diff Error</h2><p style='color:red;'>{e}</p>"

    def _run_og_banner(self):
        topic = self._topic_entry.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
            
        ds = APP.current_date if APP else today_str()
        slug = slugify(topic)
        img_dir = CONTENT_DIR / ds / slug / "images"
        img_dir.mkdir(parents=True, exist_ok=True)
        dest_file = img_dir / "og_cover.png"
        
        try:
            from PIL import Image, ImageDraw, ImageFont
            
            img = Image.new('RGB', (1200, 630), color='#1A2B4A')
            draw = ImageDraw.Draw(img)
            
            for i in range(0, 1200, 40):
                draw.line([(i, 0), (i, 630)], fill='#23395B', width=1)
            for j in range(0, 630, 40):
                draw.line([(0, j), (1200, j)], fill='#23395B', width=1)
                
            draw.rectangle([20, 20, 1180, 610], outline='#FBBF24', width=6)
            
            title_text = topic.title()
            words = title_text.split()
            lines = []
            current_line = []
            for w in words:
                if len(" ".join(current_line + [w])) > 30:
                    lines.append(" ".join(current_line))
                    current_line = [w]
                else:
                    current_line.append(w)
            if current_line:
                lines.append(" ".join(current_line))
                
            y = 180
            for line in lines[:3]:
                draw.text((80, y), line, fill='#FFFFFF', font=None, size=50)
                y += 75
                
            draw.text((80, 500), f"PUBLISHED: {ds}", fill='#FBBF24', font=None, size=24)
            draw.text((80, 540), "MAYA COLLABORATIVE RESEARCH", fill='#8E9AAF', font=None, size=18)
            
            img.save(dest_file, "PNG")
            APP.toast("Local OG Banner generated!", "ok")
            self.rerender()
            
        except Exception:
            prompt_text = f"A sleek professional blog post cover banner layout, with 16:9 aspect ratio, dark background, featuring title text: '{topic}'"
            command = f"/blog image generate \"{prompt_text}\""
            prompt = f"{command}\n\nTARGET FILE (write here, overwrite it): {dest_file}"
            if self._ask_agy_fn:
                self._loading_popup = GeneratingPopup(self.winfo_toplevel())
                self._ask_agy_fn(prompt)
                APP.toast("Pillow fallback. Querying AI image generator...", "ok")

    def _publish_article(self):
        topic = self._topic_entry.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
            
        platform = self._publish_platform_menu.get()
        draft_file = self.research_path("draft")
        
        if not draft_file.exists():
            APP.toast("Draft file does not exist! Compile a draft first.", "error")
            return
            
        content = draft_file.read_text(encoding="utf-8", errors="replace")
        title = topic.title()
        
        if platform == "GitHub / Git Repo":
            git_path = SETTINGS.get("git_repo_path", "").strip()
            if not git_path:
                APP.toast("Please configure 'Git Repo Root Path' in settings first!", "error")
                return
                
            repo_root = Path(git_path)
            if not repo_root.exists():
                APP.toast("Configured git repo path does not exist on disk!", "error")
                return
                
            target_content_dir = repo_root / "content" / "posts"
            target_content_dir.mkdir(parents=True, exist_ok=True)
            dest_post = target_content_dir / f"{slugify(topic)}.md"
            
            try:
                import shutil
                shutil.copy(draft_file, dest_post)
                src_images = draft_file.parent / "images"
                if src_images.exists():
                    dest_images = repo_root / "public" / "images" / slugify(topic)
                    dest_images.mkdir(parents=True, exist_ok=True)
                    for f in src_images.glob("*.*"):
                        shutil.copy(f, dest_images / f.name)
                        
                APP.toast("Post files exported to Git repo content folder!", "ok")
            except Exception as e:
                APP.toast(f"Export failed: {e}", "error")
                
        elif platform == "WordPress REST API":
            wp_url = SETTINGS.get("wp_url", "").strip()
            wp_user = SETTINGS.get("wp_username", "").strip()
            wp_pass = SETTINGS.get("wp_app_password", "").strip()
            
            if not wp_url or not wp_pass:
                APP.toast("WordPress URL and App Password are required in settings!", "error")
                return
                
            def do_wp_post():
                import requests
                import base64
                
                url = f"{wp_url.rstrip('/')}/wp-json/wp/v2/posts"
                credentials = f"{wp_user}:{wp_pass}"
                token = base64.b64encode(credentials.encode()).decode()
                headers = {'Authorization': f'Basic {token}'}
                
                payload = {
                    'title': title,
                    'content': content,
                    'status': 'draft'
                }
                
                try:
                    res = requests.post(url, json=payload, headers=headers, timeout=10)
                    if res.status_code == 201:
                        APP.toast("Post successfully synced to WordPress as Draft!", "ok")
                    else:
                        APP.toast(f"WordPress API error: {res.status_code} - {res.text[:100]}", "error")
                except Exception as e:
                    APP.toast(f"Failed to connect to WordPress: {e}", "error")
                    
            import threading
            threading.Thread(target=do_wp_post, daemon=True).start()
            APP.toast("Syncing with WordPress API...", "ok")
            
        elif platform == "Ghost CMS API":
            gh_url = SETTINGS.get("ghost_url", "").strip()
            gh_key = SETTINGS.get("ghost_admin_api_key", "").strip()
            
            if not gh_url or not gh_key:
                APP.toast("Ghost URL and Admin API Key are required in settings!", "error")
                return
                
            def do_ghost_post():
                import requests
                import jwt
                from datetime import datetime as dt
                
                try:
                    id_part, secret_part = gh_key.split(':')
                    iat = int(dt.now().timestamp())
                    headers = {
                        'alg': 'HS256',
                        'kid': id_part
                    }
                    payload = {
                        'iat': iat,
                        'exp': iat + 300,
                        'aud': '/admin/'
                    }
                    token = jwt.encode(payload, bytes.fromhex(secret_part), algorithm='HS256', headers=headers)
                    
                    url = f"{gh_url.rstrip('/')}/ghost/api/admin/posts/"
                    req_headers = {'Authorization': f'Ghost {token}'}
                    
                    post_payload = {
                        'posts': [{
                            'title': title,
                            'html': md_to_html(content),
                            'status': 'draft'
                        }]
                    }
                    
                    res = requests.post(url, json=post_payload, headers=req_headers, timeout=10)
                    if res.status_code == 201:
                        APP.toast("Post successfully synced to Ghost as Draft!", "ok")
                    else:
                        APP.toast(f"Ghost API error: {res.status_code} - {res.text[:100]}", "error")
                except Exception as e:
                    APP.toast(f"Ghost publishing failed: {e}", "error")
                    
            import threading
            threading.Thread(target=do_ghost_post, daemon=True).start()
            APP.toast("Syncing with Ghost API...", "ok")

    def _repurpose_socials(self):
        topic = self._topic_entry.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
            
        draft_file = self.research_path("draft")
        social_file = self.research_path("socials")
        
        if not draft_file.exists():
            APP.toast("Draft file does not exist! Repurpose requires a draft.", "error")
            return
            
        instr = (
            f"Read the finished draft at {draft_file}."
            " Repurpose this blog post into three high-engagement social media visual assets:\n"
            " 1. A promo X/Twitter Thread (exactly 5 threaded tweets with hooks and summaries).\n"
            " 2. A LinkedIn outline post (bulleted summary, custom hook, calls to action).\n"
            " 3. An email newsletter preview summary (subject line, hook body, CTA link).\n"
            " Write all three sections directly to the socials output file."
        )
        
        prompt = f"{instr}\n\nTARGET FILE (write here, overwrite it): {social_file}"
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)
            APP.toast("Repurposing draft for social threads...", "ok")

    def _run_discourse(self):
        topic = self._topic_entry.get().strip()
        focus = self._focus_entry.get().strip()
        comment = self._instr_discourse.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
        
        ds = APP.current_date if APP else today_str()
        target_file = self.research_path("discourse")
        
        if target_file.exists():
            instr = f"Update the existing discourse research data at {target_file} for topic '{topic}'."
            if comment:
                instr += f" Apply this custom update instruction: {comment}."
            instr += " Preserve all previous valid research entries, but expand or refine it accordingly."
        else:
            instr = f"Research what people are saying in the last 30 days about '{topic}' across Reddit, Twitter, Hacker News, dev.to, and YouTube."
            if focus:
                instr += f" Pay special attention to: {focus}."
            if comment:
                instr += f" Additional instruction: {comment}."
            instr += " Output a structured analysis of practitioner discussions, key friction points, and unique opinions."
        
        prompt = f"{instr}\n\nTARGET FILE (write here, overwrite it): {target_file}"
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)

    def _run_outline(self):
        topic = self._topic_entry.get().strip()
        template = self._template_menu.get()
        comment = self._instr_outline.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
        
        ds = APP.current_date if APP else today_str()
        outline_file = self.research_path("outline")
        discourse_file = self.research_path("discourse")
        
        if outline_file.exists():
            instr = f"Update the existing content outline at {outline_file} for topic '{topic}'."
            if comment:
                instr += f" Apply this custom feedback/tweak: {comment}."
            instr += " Make sure you output the complete updated outline (H2/H3 levels with section word counts)."
        else:
            instr = f"Generate a detailed SERP-informed content outline (headings H2, H3) for a '{template}' on '{topic}'."
            if discourse_file.exists():
                instr += f" Load and read the research data from {discourse_file} and inject practitioner viewpoints, issues, and quotes."
            if comment:
                instr += f" Special outline instructions: {comment}."
            instr += " Specify word count targets per section. Do not explain, just write the outline."
        
        prompt = f"{instr}\n\nTARGET FILE (write here, overwrite it): {outline_file}"
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)

    def _run_draft(self):
        topic = self._topic_entry.get().strip()
        template = self._template_menu.get()
        comment = self._instr_draft.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
        
        ds = APP.current_date if APP else today_str()
        draft_file = self.research_path("draft")
        outline_file = self.research_path("outline")
        prompts_file = self.research_path("image_prompts")
        img_dir = CONTENT_DIR / ds / slugify(topic) / "images"
        
        image_list_str = ""
        if img_dir.exists():
            images = list(img_dir.glob("*.*"))
            if images:
                image_list_str = "\nAvailable images in workspace:\n" + "\n".join([f"- images/{im.name}" for im in images])
        
        if draft_file.exists():
            import shutil
            try:
                shutil.copy(draft_file, self.research_path("draft_bak"))
            except Exception:
                pass
            instr = f"Read and update the existing draft at {draft_file}."
            if comment:
                instr += f" Apply this user rewrite/edit feedback: {comment}."
            instr += " Preserve all other sections of the article completely unchanged."
        else:
            instr = f"Write a complete, high-quality article for a '{template}' on the topic '{topic}'."
            if outline_file.exists():
                instr += f" Read and strictly follow the custom section structures and word count targets in: {outline_file}."
            if comment:
                instr += f" Additional drafting instructions: {comment}."
            instr += (
                " Apply E-E-A-T guidelines, use Answer-First Formatting for every H2 (open with a 40-60 word statistic-rich paragraph). "
                "Every statistic must cite a named source. Keep paragraphs under 150 words."
            )
        
        if image_list_str:
            instr += f"\n{image_list_str}\nPlease reference these images in the draft where appropriate using standard markdown syntax: `![Caption](images/filename.png)`."
            
        instr += (
            f"\n\nIn addition to the draft, analyze the article and write a list of exactly 5 detailed, high-quality image prompts to the file: {prompts_file}."
            " Use exactly this JSON format for the prompts:\n"
            "[\n"
            "  { \"id\": 1, \"prompt\": \"Detailed description of visual asset 1\" },\n"
            "  { \"id\": 2, \"prompt\": \"Detailed description of visual asset 2\" }\n"
            "]\n"
            "Do not explain, just write the draft file and write the image prompts JSON file."
        )
        
        prompt = f"{instr}\n\nTARGET FILE (write here, overwrite it): {draft_file}"
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)

    def _run_qa(self):
        topic = self._topic_entry.get().strip()
        comment = self._instr_review.get().strip()
        if not topic:
            APP.toast("Topic/Keyword is required!", "error")
            return
            
        ds = APP.current_date if APP else today_str()
        draft_file = self.research_path("draft")
        review_file = self.research_path("review")
        if not draft_file.exists():
            APP.toast("Draft file does not exist! Generate the draft first.", "error")
            return
        
        instr = f"Perform a fact-check and SEO quality audit on the draft at {draft_file}."
        if comment:
            instr += f" Apply this specific audit focus/instruction: {comment}."
        instr += (
            " Verify every statistical claim against named sources and check headings, title tag, and keyword density."
            " Output a 100-point score breakdown across: Content Quality, SEO, E-E-A-T, Technical, and AI Citation Readiness."
            " Detail any failed checks or unverified claims."
        )
        
        prompt = f"{instr}\n\nTARGET FILE (write here, overwrite it): {review_file}"
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(prompt)


# ── Interactive base (JSON-backed, file-watching) ──────────────────────────────

class JsonTab(ctk.CTkFrame):
    POLL_MS = 900
    KIND: str = ""

    def __init__(self, parent, ask_agy_fn=None):
        super().__init__(parent, fg_color="transparent")
        self._ask_agy_fn = ask_agy_fn
        self._last_mtime = -1.0
        self.data = self._default()
        self.grid_columnconfigure(0, weight=1)
        self._build()
        self._load_now()
        self._poll()

    # subclasses override
    def _default(self): return {}
    def _instruction_key(self): return ""
    def _build(self): ...
    def render(self): ...

    @property
    def path(self) -> Path:
        return path_for(self.KIND, APP.current_date if APP else today_str())

    def _ask(self):
        instr = SETTINGS.get(self._instruction_key(), "")
        ds = APP.current_date if APP else today_str()
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(build_prompt(instr, self.KIND, ds))
        else:
            launch_agy()

    def _edit_instr(self):
        open_instr_editor(self.winfo_toplevel(), self._instruction_key(), self.KIND.replace("_", " ").title())

    def _save(self):
        backup_file(self.path)
        self._last_mtime = save_json(self.path, self.data)
        self.render()

    def _load_now(self):
        """Load current date's file; reset to default if absent."""
        p = self.path
        if p.exists():
            loaded = load_json(p, None)
            ok, fixed, msg = validate_and_fix(self.KIND, loaded)
            if ok:
                self.data = fixed
            else:
                self.data = self._default()
                if APP:
                    APP.toast(f"⚠ {msg}", "error")
            try:
                self._last_mtime = p.stat().st_mtime
            except Exception:
                self._last_mtime = -1.0
        else:
            self.data = self._default()
            self._last_mtime = -1.0
        self.render()

    def on_date_change(self):
        self._last_mtime = -2.0
        self._load_now()

    def _poll(self):
        try:
            p = self.path
            if p.exists():
                m = p.stat().st_mtime
                if m != self._last_mtime:
                    self._last_mtime = m
                    loaded = load_json(p, None)
                    ok, fixed, msg = validate_and_fix(self.KIND, loaded)
                    if ok:
                        self.data = fixed
                        self.render()
                    elif APP:
                        APP.toast(f"⚠ {msg} — keeping previous", "error")
        except Exception:
            pass
        self.after(self.POLL_MS, self._poll)


# ── Plan Tab ───────────────────────────────────────────────────────────────────

PRIORITY_STYLE = {
    "high":   (RED_SOFT, RED, "High"),
    "medium": (YOLK_SOFT, YOLK_DK, "Med"),
    "low":    (BLUE_SOFT, BLUE, "Low"),
}

class PlanTab(JsonTab):
    KIND = "plan"

    def _default(self):
        return {"date": TODAY, "sections": [
            {"name": "Morning", "tasks": []},
            {"name": "Afternoon", "tasks": []},
            {"name": "Evening", "tasks": []},
        ]}

    def _instruction_key(self): return "plan_instruction"

    def _build(self):
        self.grid_rowconfigure(2, weight=1)

        hdr = TabHeader(self, "Today's Plan", f"Structured day · {TODAY}", "plan")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        self._btn_ask = pill_button(hdr.actions, "Generate with agy", self._ask, "accent",
                    "sparkles", "ink")
        self._btn_ask.grid(row=0, column=0, padx=4)
        pill_button(hdr.actions, "Edit instruction", self._edit_instr, "ghost",
                    "edit", "ink").grid(row=0, column=1, padx=4)

        # stats row
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 8))
        for i in range(4):
            bar.grid_columnconfigure(i, weight=1)
        self._chip_total = StatChip(bar, "Total Tasks", 0, BLUE, BLUE_SOFT, "circle")
        self._chip_done  = StatChip(bar, "Completed", 0, GREEN, GREEN_SOFT, "circle_check")
        self._chip_left  = StatChip(bar, "Remaining", 0, YOLK_DK, YOLK_SOFT, "clock")
        self._chip_pct   = StatChip(bar, "Progress", "0%", BLUE, BLUE_SOFT, "trending")
        for i, c in enumerate([self._chip_total, self._chip_done, self._chip_left, self._chip_pct]):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))

        self._progress = ctk.CTkProgressBar(self, height=10, corner_radius=6,
                                            fg_color=BG2, progress_color=YOLK)
        self._progress.grid(row=1, column=0, sticky="ew", padx=22, pady=(78, 0))
        self._progress.set(0)

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=18, pady=(14, 8))
        self._scroll.grid_columnconfigure(0, weight=1)

        # add-task row
        add = card_frame(self)
        add.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 16))
        add.grid_columnconfigure(0, weight=1)
        self._entry = ctk.CTkEntry(add, placeholder_text="Add a task…", height=40,
                                   font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER,
                                   text_color=INK, corner_radius=10)
        self._entry.grid(row=0, column=0, sticky="ew", padx=(12, 8), pady=10)
        self._entry.bind("<Return>", lambda e: self._add())
        self._sec_var = ctk.StringVar(value="Morning")
        self._sec_menu = ctk.CTkOptionMenu(add, variable=self._sec_var, values=["Morning"],
                                           width=140, height=40, font=(FONT_BODY, 12),
                                           fg_color=BLUE_SOFT, button_color=BLUE,
                                           button_hover_color=BLUE_DK, text_color=INK,
                                           dropdown_fg_color=CARD, dropdown_text_color=INK)
        self._sec_menu.grid(row=0, column=1, padx=6, pady=10)
        pill_button(add, "Add", self._add, "primary", "plus", "cream", width=90).grid(
            row=0, column=2, padx=(6, 12), pady=10)

        self.render()

    def _sections(self):
        return self.data.get("sections", [])

    def _add(self):
        title = self._entry.get().strip()
        if not title:
            return
        sec_name = self._sec_var.get()
        for s in self._sections():
            if s.get("name") == sec_name:
                s.setdefault("tasks", []).append(
                    {"id": new_id(), "title": title, "done": False, "priority": "medium"})
                break
        self._entry.delete(0, "end")
        self._save()

    def _toggle(self, task):
        task["done"] = not task.get("done", False)
        self._save()

    def _cycle_priority(self, task):
        order = ["high", "medium", "low"]
        cur = task.get("priority", "medium")
        task["priority"] = order[(order.index(cur) + 1) % 3] if cur in order else "medium"
        self._save()

    def _delete(self, section, task):
        section.get("tasks", []).remove(task)
        self._save()

    def _edit(self, task):
        EditDialog(self.winfo_toplevel(), "Edit task",
                   [("title", "Title", "entry", None),
                    ("priority", "Priority", "option", ["high", "medium", "low"])],
                   task, lambda v: (task.update(title=v["title"], priority=v["priority"]), self._save()))

    def _move(self, section, task, delta):
        if move_in_list(section.get("tasks", []), task, delta):
            self._save()

    def _promote(self, task):
        ds = APP.current_date if APP else today_str()
        p = path_for("activities", ds)
        data = load_json(p, {"tasks": [], "recommendations": []})
        ok, data, _ = validate_and_fix("activities", data)
        if not ok:
            data = {"tasks": [], "recommendations": []}
        if any(t["title"] == task["title"] for t in data.get("tasks", [])):
            if APP: APP.toast("Already in Activities", "info")
            return
        data["tasks"].append({"id": new_id(), "title": task["title"],
                               "status": "done" if task.get("done") else "active", "note": ""})
        backup_file(p)
        save_json(p, data)
        if APP: APP.toast(f"→ Activities: {task['title'][:50]}", "ok")

    def render(self):
        if hasattr(self, "_loading_popup") and self._loading_popup:
            try:
                self._loading_popup.destroy()
            except Exception:
                pass
            self._loading_popup = None
        if hasattr(self, "_btn_ask"):
            self._btn_ask.configure(text="  Generate with agy", state="normal")
        names = [s.get("name", "?") for s in self._sections()] or ["Morning"]
        self._sec_menu.configure(values=names)
        if self._sec_var.get() not in names:
            self._sec_var.set(names[0])

        for w in self._scroll.winfo_children():
            w.destroy()

        total = done = 0
        row = 0
        for section in self._sections():
            tasks = section.get("tasks", [])
            sec_done = sum(1 for t in tasks if t.get("done"))
            total += len(tasks); done += sec_done

            head = ctk.CTkFrame(self._scroll, fg_color="transparent")
            head.grid(row=row, column=0, sticky="ew", pady=(10, 2), padx=4)
            head.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(head, text=section.get("name", "—").upper(),
                         font=(FONT_HEAD, 14, "bold"), text_color=BLUE).grid(row=0, column=0, sticky="w")
            ctk.CTkLabel(head, text=f"{sec_done}/{len(tasks)}",
                         font=(FONT_BODY, 12), text_color=DIM).grid(row=0, column=2, sticky="e")
            row += 1

            if not tasks:
                ctk.CTkLabel(self._scroll, text="   No tasks here yet.",
                             font=(FONT_BODY, 12, "italic"), text_color=DIM, anchor="w").grid(
                    row=row, column=0, sticky="ew", padx=10, pady=2)
                row += 1
            for t in tasks:
                self._task_card(t, section).grid(row=row, column=0, sticky="ew", pady=4, padx=2)
                row += 1

        self._chip_total.set(total)
        self._chip_done.set(done)
        self._chip_left.set(total - done)
        pct = int(done / total * 100) if total else 0
        self._chip_pct.set(f"{pct}%")
        self._progress.set(pct / 100)

    def _task_card(self, task, section):
        c = card_frame(self._scroll)
        c.grid_columnconfigure(1, weight=1)
        done = task.get("done", False)

        chk = ctk.CTkButton(
            c, text="", width=34, height=34, corner_radius=17,
            fg_color=GREEN_SOFT if done else CARD2,
            hover_color=GREEN_SOFT if done else BLUE_SOFT,
            border_width=2, border_color=GREEN if done else BORDER,
            image=icon("circle_check" if done else "circle", "green" if done else "dim", 20),
            command=lambda: self._toggle(task))
        chk.grid(row=0, column=0, padx=(12, 10), pady=10)

        lbl = ctk.CTkLabel(c, text=task.get("title", ""), anchor="w",
                     font=(FONT_BODY, 14, "overstrike" if done else "normal"),
                     text_color=DIM if done else INK, wraplength=560)
        lbl.grid(row=0, column=1, sticky="w", pady=10)
        lbl.bind("<Double-Button-1>", lambda e: self._edit(task))

        pr = task.get("priority", "medium")
        ptint, pcol, plabel = PRIORITY_STYLE.get(pr, PRIORITY_STYLE["medium"])
        ctk.CTkButton(c, text=plabel, width=54, height=26, corner_radius=8,
                      fg_color=ptint, hover_color=ptint, text_color=pcol,
                      font=(FONT_BODY, 11, "bold"),
                      command=lambda: self._cycle_priority(task)).grid(row=0, column=2, padx=6)

        reorder_buttons(c, lambda: self._move(section, task, -1),
                        lambda: self._move(section, task, 1)).grid(row=0, column=3, padx=2)
        ctk.CTkButton(c, text="", width=30, height=30, corner_radius=8,
                      fg_color="transparent", hover_color=BLUE_SOFT,
                      image=icon("edit", "dim", 16),
                      command=lambda: self._edit(task)).grid(row=0, column=4, padx=2)
        ctk.CTkButton(c, text="↗", width=34, height=30, corner_radius=8,
                      fg_color="transparent", hover_color=GREEN_SOFT,
                      text_color=DIM, font=(FONT_BODY, 13, "bold"),
                      command=lambda: self._promote(task)).grid(row=0, column=5, padx=2)
        ctk.CTkButton(c, text="", width=30, height=30, corner_radius=8,
                      fg_color="transparent", hover_color=RED_SOFT,
                      image=icon("trash", "dim", 16),
                      command=lambda: self._delete(section, task)).grid(row=0, column=6, padx=(2, 10))
        return c


# ── Activities Tab ─────────────────────────────────────────────────────────────

STATUS_ORDER = ["active", "pending", "done", "blocked"]
STATUS_STYLE = {
    "active":  (BLUE_SOFT, BLUE, "Active", "clock"),
    "pending": (YOLK_SOFT, YOLK_DK, "Pending", "circle"),
    "done":    (GREEN_SOFT, GREEN, "Done", "circle_check"),
    "blocked": (RED_SOFT, RED, "Blocked", "blocked"),
}

_PROJECT_STATUS_COLOR = {
    "active":   GREEN,  "paused":   YOLK_DK,
    "completed": BLUE,  "archived": DIM,
}

class ActivitiesTab(ctk.CTkFrame):

    def __init__(self, parent, ask_agy_fn=None):
        super().__init__(parent, fg_color="transparent")
        self._ask_agy_fn = ask_agy_fn
        self._selected_slug = None
        self._projects = []
        self._proj_btns = {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self.after(200, self._load_projects)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build(self):
        hdr = TabHeader(self, "Activities", "Project intelligence · agy history · Upwork inbox", "activities")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        pill_button(hdr.actions, "Update CONTEXT", self._update_context, "accent",
                    "sparkles", "ink").grid(row=0, column=0, padx=4)
        pill_button(hdr.actions, "Refresh", self._load_projects, "ghost",
                    "refresh", "ink").grid(row=0, column=1, padx=4)
        pill_button(hdr.actions, "+ Project", self._add_project_dialog, "ghost",
                    "plus", "ink").grid(row=0, column=2, padx=4)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 16))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # Left: project list
        left = ctk.CTkFrame(body, fg_color=CARD, corner_radius=14,
                            border_width=1, border_color=BORDER, width=230)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 10))
        left.grid_propagate(False)
        left.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(left, text="PROJECTS", font=(FONT_BODY, 10, "bold"),
                     text_color=DIM).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 6))
        self._proj_scroll = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self._proj_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=(0, 8))
        self._proj_scroll.grid_columnconfigure(0, weight=1)

        # Right: detail panel
        self._detail = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self._detail.grid(row=0, column=1, sticky="nsew")
        self._detail.grid_columnconfigure(0, weight=1)
        self._show_placeholder()

    # ── Project list ──────────────────────────────────────────────────────────

    def _load_projects(self):
        reg = load_registry()
        self._projects = reg.get("projects", [])
        for w in self._proj_scroll.winfo_children():
            w.destroy()
        self._proj_btns = {}
        active = [p for p in self._projects if p.get("status") != "archived"]
        for p in active:
            self._proj_btns[p["slug"]] = self._make_proj_btn(p)
        # restore selection or pick first
        if self._selected_slug and self._selected_slug in self._proj_btns:
            self._select_project(self._selected_slug)
        elif active:
            self._select_project(active[0]["slug"])

    def _make_proj_btn(self, p):
        slug = p["slug"]
        color = _PROJECT_STATUS_COLOR.get(p.get("status", "active"), DIM)
        last = p.get("last_agy_date", "")
        msgs = p.get("agy_msg_count", 0)
        inbox_count = sum(1 for i in load_inbox(7)
                         if p["path"].lower() in i.get("body","").lower()
                         or p["name"].lower() in i.get("subject","").lower())

        btn = ctk.CTkButton(
            self._proj_scroll, text="", anchor="w", height=62, corner_radius=10,
            fg_color="transparent", hover_color=BG2,
            command=lambda s=slug: self._select_project(s))
        btn.grid(sticky="ew", pady=2, padx=4)

        inner = ctk.CTkFrame(btn, fg_color="transparent")
        inner.place(relx=0, rely=0, relwidth=1, relheight=1)
        inner.grid_columnconfigure(1, weight=1)

        dot = ctk.CTkFrame(inner, fg_color=color, corner_radius=5, width=8, height=8)
        dot.grid(row=0, column=0, padx=(12, 8), pady=(14, 0), sticky="n")
        dot.grid_propagate(False)

        name_lbl = ctk.CTkLabel(inner, text=p["name"], font=(FONT_BODY, 13, "bold"),
                                text_color=INK, anchor="w")
        name_lbl.grid(row=0, column=1, sticky="w", pady=(12, 0))

        meta = f"{msgs} agy msgs"
        if last: meta += f"  ·  {last}"
        if inbox_count: meta += f"  ·  {inbox_count} inbox"
        ctk.CTkLabel(inner, text=meta, font=(FONT_BODY, 10), text_color=DIM, anchor="w").grid(
            row=1, column=1, sticky="w", pady=(0, 10))

        for w in (btn, inner, name_lbl):
            w.bind("<Button-1>", lambda e, s=slug: self._select_project(s))
        return btn

    def _select_project(self, slug):
        self._selected_slug = slug
        for s, b in self._proj_btns.items():
            b.configure(fg_color=BLUE_SOFT if s == slug else "transparent",
                        hover_color=BLUE_SOFT if s == slug else BG2)
        proj = next((p for p in self._projects if p["slug"] == slug), None)
        if proj:
            self._show_project(proj)

    # ── Detail panel ──────────────────────────────────────────────────────────

    def _show_placeholder(self):
        for w in self._detail.winfo_children(): w.destroy()
        ctk.CTkLabel(self._detail, text="Select a project →",
                     font=(FONT_BODY, 14, "italic"), text_color=DIM).grid(row=0, column=0, pady=40)

    def _show_project(self, p):
        for w in self._detail.winfo_children(): w.destroy()
        row = 0

        # ── Project header ────────────────────────────────────────────────────
        ph = card_frame(self._detail)
        ph.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
        ph.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(ph, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 4))
        top.grid_columnconfigure(0, weight=1)
        color = _PROJECT_STATUS_COLOR.get(p.get("status","active"), DIM)
        ctk.CTkLabel(top, text=p["name"], font=(FONT_HEAD, 20, "bold"), text_color=INK).grid(
            row=0, column=0, sticky="w")
        ctk.CTkButton(top, text=p.get("status","active").upper(), width=90, height=28,
                      corner_radius=8, fg_color=color, hover_color=color,
                      text_color="#FFF", font=(FONT_BODY, 11, "bold"),
                      command=lambda: self._cycle_status(p)).grid(row=0, column=1, padx=(8,0))
        ctk.CTkLabel(ph, text=p.get("path",""), font=("Consolas", 11), text_color=DIM, anchor="w").grid(
            row=1, column=0, sticky="w", padx=16, pady=(0, 4))

        btns_row = ctk.CTkFrame(ph, fg_color="transparent")
        btns_row.grid(row=2, column=0, sticky="w", padx=12, pady=(0, 12))
        pill_button(btns_row, "Open in agy", lambda pp=p: self._open_in_agy(pp),
                    "primary", "sparkles", "cream").pack(side="left", padx=4)
        pill_button(btns_row, "Brief agy", lambda pp=p: self._brief_agy(pp),
                    "accent", "send", "ink").pack(side="left", padx=4)
        pill_button(btns_row, "Edit", lambda pp=p: self._edit_project(pp),
                    "ghost", "edit", "ink").pack(side="left", padx=4)

        # ── Next Actions ──────────────────────────────────────────────────────
        row = self._section(row, "Next Actions")
        na_card = card_frame(self._detail)
        na_card.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
        na_card.grid_columnconfigure(0, weight=1)
        actions = p.get("next_actions", [])
        if not actions:
            ctk.CTkLabel(na_card, text="No next actions. Add one below.",
                         font=(FONT_BODY, 12, "italic"), text_color=DIM).grid(
                row=0, column=0, padx=16, pady=10, sticky="w")
        for i, act in enumerate(actions):
            ar = ctk.CTkFrame(na_card, fg_color="transparent")
            ar.grid(row=i, column=0, sticky="ew", padx=12, pady=3)
            ar.grid_columnconfigure(1, weight=1)
            ctk.CTkButton(ar, text="✓", width=28, height=28, corner_radius=8,
                          fg_color=GREEN_SOFT, hover_color=GREEN_SOFT, text_color=GREEN,
                          font=(FONT_BODY, 12, "bold"),
                          command=lambda a=act, pp=p: self._done_action(pp, a)).grid(row=0, column=0, padx=(0,8))
            ctk.CTkLabel(ar, text=act, font=(FONT_BODY, 13), text_color=INK, anchor="w").grid(
                row=0, column=1, sticky="w")
            ctk.CTkButton(ar, text="✕", width=24, height=24, corner_radius=6,
                          fg_color="transparent", hover_color=RED_SOFT, text_color=DIM,
                          font=(FONT_BODY, 11),
                          command=lambda a=act, pp=p: self._del_action(pp, a)).grid(row=0, column=2)

        add_row = ctk.CTkFrame(na_card, fg_color="transparent")
        add_row.grid(row=len(actions)+1, column=0, sticky="ew", padx=12, pady=(6, 10))
        add_row.grid_columnconfigure(0, weight=1)
        entry = ctk.CTkEntry(add_row, placeholder_text="Add next action…", height=34,
                             font=(FONT_BODY, 12), fg_color=CARD2, border_color=BORDER,
                             text_color=INK, corner_radius=8)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda e, pp=p, en=entry: self._add_action(pp, en))
        pill_button(add_row, "Add", lambda pp=p, en=entry: self._add_action(pp, en),
                    "primary", "plus", "cream", width=70).grid(row=0, column=1)

        # ── Upwork Inbox ──────────────────────────────────────────────────────
        inbox_items = [i for i in load_inbox(30)
                       if p["path"].lower() in i.get("body","").lower()
                       or p["name"].lower() in i.get("subject","").lower()
                       or "upwork" in i.get("source","")]
        row = self._section(row, f"Upwork Inbox ({len(inbox_items)})")
        if not inbox_items:
            empty = card_frame(self._detail)
            empty.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
            gmail_status = "Gmail not configured — see Setup below" if not is_configured() else "No Upwork messages yet"
            ctk.CTkLabel(empty, text=gmail_status, font=(FONT_BODY, 12, "italic"),
                         text_color=DIM).grid(row=0, column=0, padx=16, pady=12, sticky="w")
        else:
            for item in inbox_items[:8]:
                ic = self._inbox_card(item)
                ic.grid(row=row, column=0, sticky="ew", pady=3); row += 1

        # ── agy History ───────────────────────────────────────────────────────
        history = get_all_project_history(p["path"], limit=20)
        row = self._section(row, f"agy / Claude History ({len(history)} recent)")
        if not history:
            empty2 = card_frame(self._detail)
            empty2.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
            ctk.CTkLabel(empty2, text="No agy history for this project path.",
                         font=(FONT_BODY, 12, "italic"), text_color=DIM).grid(
                row=0, column=0, padx=16, pady=12, sticky="w")
        else:
            for entry in history[:15]:
                hc = self._history_card(entry)
                hc.grid(row=row, column=0, sticky="ew", pady=2); row += 1

        # ── Notes ─────────────────────────────────────────────────────────────
        if p.get("notes"):
            row = self._section(row, "Notes")
            nc = card_frame(self._detail)
            nc.grid(row=row, column=0, sticky="ew", pady=(0, 10)); row += 1
            ctk.CTkLabel(nc, text=p["notes"], font=(FONT_BODY, 13), text_color=INK2,
                         wraplength=700, anchor="w", justify="left").grid(
                row=0, column=0, padx=16, pady=12, sticky="w")

    def _section(self, row, title):
        ctk.CTkLabel(self._detail, text=title, font=(FONT_HEAD, 14, "bold"),
                     text_color=BLUE, anchor="w").grid(
            row=row, column=0, sticky="w", pady=(14, 4)); return row + 1

    def _inbox_card(self, item):
        c = card_frame(self._detail)
        c.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(c, text=item.get("date",""), font=(FONT_BODY, 11),
                     text_color=DIM, width=90).grid(row=0, column=0, padx=(14,8), pady=10)
        box = ctk.CTkFrame(c, fg_color="transparent")
        box.grid(row=0, column=1, sticky="ew", pady=8)
        box.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(box, text=item.get("subject",""), font=(FONT_BODY, 13, "bold"),
                     text_color=INK, anchor="w").grid(row=0, column=0, sticky="w")
        if item.get("snippet"):
            ctk.CTkLabel(box, text=item["snippet"][:120], font=(FONT_BODY, 11),
                         text_color=DIM, anchor="w").grid(row=1, column=0, sticky="w")
        action = item.get("action","")
        if action:
            ctk.CTkLabel(c, text=f"→ {action}", font=(FONT_BODY, 11, "bold"),
                         fg_color=YOLK_SOFT, text_color=YOLK_DK, corner_radius=6).grid(
                row=0, column=2, padx=(8,14))
        return c

    def _history_card(self, entry):
        c = ctk.CTkFrame(self._detail, fg_color=BG2, corner_radius=8)
        c.grid_columnconfigure(2, weight=1)
        src_color = BLUE if entry.get("source") == "agy" else GREEN
        ctk.CTkLabel(c, text=entry.get("source","agy").upper(), font=(FONT_BODY, 9, "bold"),
                     fg_color=src_color, text_color="#FFF", corner_radius=4, width=46).grid(
            row=0, column=0, padx=(10,6), pady=8)
        ctk.CTkLabel(c, text=entry.get("date",""), font=(FONT_BODY, 10),
                     text_color=DIM, width=110).grid(row=0, column=1, padx=(0,8))
        ctk.CTkLabel(c, text=entry.get("text",""), font=(FONT_BODY, 12), text_color=INK2,
                     anchor="w", wraplength=600).grid(row=0, column=2, sticky="w", padx=(0,12), pady=8)
        return c

    # ── Project actions ───────────────────────────────────────────────────────

    def _cycle_status(self, p):
        order = ["active", "paused", "completed", "archived"]
        cur = p.get("status", "active")
        p["status"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "active"
        self._save_registry()
        self._load_projects()

    def _add_action(self, p, entry_widget):
        text = entry_widget.get().strip()
        if not text: return
        p.setdefault("next_actions", []).append(text)
        entry_widget.delete(0, "end")
        self._save_registry()
        self._show_project(p)

    def _done_action(self, p, action):
        p.get("next_actions", []).remove(action)
        self._save_registry()
        self._show_project(p)

    def _del_action(self, p, action):
        p.get("next_actions", []).remove(action)
        self._save_registry()
        self._show_project(p)

    def _edit_project(self, p):
        EditDialog(self.winfo_toplevel(), f"Edit — {p['name']}",
                   [("name", "Name", "entry", None),
                    ("client", "Client", "entry", None),
                    ("platform", "Platform", "option", ["upwork", "local", "other"]),
                    ("notes", "Notes", "text", None)],
                   p, lambda v: (p.update(v), self._save_registry(), self._load_projects()))

    def _save_registry(self):
        reg = load_registry()
        reg["projects"] = self._projects
        save_registry(reg)

    def _add_project_dialog(self):
        import re as _re
        EditDialog(self.winfo_toplevel(), "Add Project",
                   [("name", "Project Name", "entry", None),
                    ("path", "Path (e.g. D:\\MyProject)", "entry", None),
                    ("platform", "Platform", "option", ["upwork", "local", "other"]),
                    ("client", "Client", "entry", None)],
                   {}, lambda v: self._create_project(v))

    def _create_project(self, v):
        import re as _re
        name = v.get("name","").strip()
        path = v.get("path","").strip()
        if not name or not path: return
        slug = _re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        reg = load_registry()
        reg.setdefault("projects", []).insert(0, {
            "slug": slug, "name": name, "path": path,
            "status": "active", "platform": v.get("platform","upwork"),
            "client": v.get("client",""), "notes": "",
            "next_actions": [], "last_agy_date": "", "agy_msg_count": 0,
            "recent_prompts": [], "created_at": datetime.now().strftime("%Y-%m-%d"),
        })
        save_registry(reg)
        self._load_projects()

    def _open_in_agy(self, p):
        agy = BASE_DIR.parent / "AppData/Local/agy/bin/agy.exe"
        exe = str(agy) if agy.exists() else "agy"
        _launch_console(exe, cwd=p["path"])

    def _brief_agy(self, p):
        ctx_file = BASE_DIR / "agy_workspace" / "CONTEXT.md"
        if ctx_file.exists():
            brief = ctx_file.read_text(encoding="utf-8")[:1200]
        else:
            brief = f"Working on project: {p['name']} at {p['path']}"
        if self._ask_agy_fn:
            self._ask_agy_fn(brief)
        if APP: APP.toast("Context sent to agy terminal", "ok")

    def _update_context(self):
        def _run():
            try:
                write_context()
                self.after(0, lambda: APP.toast("CONTEXT.md updated", "ok") if APP else None)
            except Exception as e:
                self.after(0, lambda: APP.toast(f"Context error: {e}", "error") if APP else None)
        threading.Thread(target=_run, daemon=True).start()

    # ── Compat stubs for DashboardApp ─────────────────────────────────────────
    def on_date_change(self): self._load_projects()
    def render(self): pass


# ── Lessons Tab ────────────────────────────────────────────────────────────────

class LessonsTab(ctk.CTkFrame):
    """W3Schools-style course view: sidebar of chapters aggregated across
    every content/<date>/lessons.json, reading pane for the selected one."""
    POLL_MS = 1500

    def __init__(self, parent, ask_agy_fn=None):
        super().__init__(parent, fg_color="transparent")
        self._ask_agy_fn = ask_agy_fn
        self._chapters = []   # flat list: {"date": ds, "lesson": {...}}
        self._selected = 0
        self._last_mtime = -1.0
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self._build()
        self._load_all()
        self._poll()

    def _build(self):
        hdr = TabHeader(self, "Lessons", "Your AI learning course", "lessons")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        self._btn_ask = pill_button(hdr.actions, "Generate with agy", self._ask, "accent",
                    "sparkles", "ink")
        self._btn_ask.grid(row=0, column=0, padx=4)
        pill_button(hdr.actions, "Edit instruction", self._edit_instr, "ghost",
                    "edit", "ink").grid(row=0, column=1, padx=4)
        pill_button(hdr.actions, "Refresh", self._load_all, "ghost",
                    "refresh", "ink").grid(row=0, column=2, padx=4)

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 6))
        for i in range(3):
            bar.grid_columnconfigure(i, weight=1)
        self._chip_total = StatChip(bar, "Chapters", 0, BLUE, BLUE_SOFT, "lessons")
        self._chip_learn = StatChip(bar, "Learned", 0, GREEN, GREEN_SOFT, "circle_check")
        self._chip_pct   = StatChip(bar, "Mastery", "0%", YOLK_DK, YOLK_SOFT, "trending")
        for i, c in enumerate([self._chip_total, self._chip_learn, self._chip_pct]):
            c.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))

        self._progress = ctk.CTkProgressBar(self, height=10, corner_radius=6,
                                            fg_color=BG2, progress_color=GREEN)
        self._progress.grid(row=1, column=0, sticky="ew", padx=22, pady=(78, 0))
        self._progress.set(0)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=18, pady=(14, 16))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self._sidebar = ctk.CTkScrollableFrame(body, fg_color=CARD, corner_radius=12,
                                               border_width=1, border_color=BORDER, width=250)
        self._sidebar.grid(row=0, column=0, sticky="ns", padx=(0, 14))
        self._sidebar.grid_columnconfigure(0, weight=1)

        self._reading = ctk.CTkScrollableFrame(body, fg_color="transparent")
        self._reading.grid(row=0, column=1, sticky="nsew")
        self._reading.grid_columnconfigure(0, weight=1)

    # ── agy / instruction ──
    def _ask(self):
        instr = SETTINGS.get("lessons_instruction", "")
        ds = APP.current_date if APP else today_str()
        if self._ask_agy_fn:
            self._loading_popup = GeneratingPopup(self.winfo_toplevel())
            self._ask_agy_fn(build_prompt(instr, "lessons", ds))
        else:
            launch_agy()

    def _edit_instr(self):
        open_instr_editor(self.winfo_toplevel(), "lessons_instruction", "Lessons")

    @property
    def _current_path(self) -> Path:
        return path_for("lessons", APP.current_date if APP else today_str())

    def on_date_change(self):
        self._load_all()

    # ── data ──
    def _load_all(self):
        self._chapters = []
        for d in sorted(list_history_dates(), reverse=True):
            data = load_json(path_for("lessons", d), {})
            if not data:
                continue
            ok, fixed, _ = validate_and_fix("lessons", data)
            if not ok:
                continue
            for les in fixed.get("lessons", []):
                self._chapters.append({"date": d, "lesson": les})
        if self._selected >= len(self._chapters):
            self._selected = max(0, len(self._chapters) - 1)
        try:
            p = self._current_path
            self._last_mtime = p.stat().st_mtime if p.exists() else -1.0
        except Exception:
            self._last_mtime = -1.0
        self.render()

    def _poll(self):
        try:
            p = self._current_path
            m = p.stat().st_mtime if p.exists() else -1.0
            if m != self._last_mtime:
                self._load_all()
        except Exception:
            pass
        self.after(self.POLL_MS, self._poll)

    def _save_chapter(self, ch):
        """Persist an edit/learned-toggle for one chapter back to its own date's file."""
        d = ch["date"]
        p = path_for("lessons", d)
        data = load_json(p, {"date": d, "lessons": []})
        ok, fixed, _ = validate_and_fix("lessons", data)
        if not ok:
            fixed = {"date": d, "lessons": []}
        lid = ch["lesson"]["id"]
        for l in fixed.get("lessons", []):
            if l["id"] == lid:
                l.update(ch["lesson"])
                break
        backup_file(p)
        save_json(p, fixed)
        self.render()

    def _toggle(self, ch):
        ch["lesson"]["learned"] = not ch["lesson"].get("learned", False)
        self._save_chapter(ch)

    def _edit(self, ch):
        les = ch["lesson"]
        EditDialog(self.winfo_toplevel(), "Edit lesson",
                   [("title", "Title", "entry", None),
                    ("what", "What", "text", None),
                    ("example", "Example", "text", None),
                    ("action", "Action", "text", None)],
                   les, lambda v: (les.update(v), self._save_chapter(ch)))

    def _select(self, idx):
        self._selected = idx
        self.render()

    # ── render ──
    def render(self):
        if hasattr(self, "_loading_popup") and self._loading_popup:
            try:
                self._loading_popup.destroy()
            except Exception:
                pass
            self._loading_popup = None
        if hasattr(self, "_btn_ask"):
            self._btn_ask.configure(text="  Generate with agy", state="normal")
        for w in self._sidebar.winfo_children():
            w.destroy()
        for w in self._reading.winfo_children():
            w.destroy()

        total = len(self._chapters)
        learned = sum(1 for c in self._chapters if c["lesson"].get("learned"))
        self._chip_total.set(total)
        self._chip_learn.set(learned)
        pct = int(learned / total * 100) if total else 0
        self._chip_pct.set(f"{pct}%")
        self._progress.set(pct / 100)

        if not total:
            ctk.CTkLabel(self._sidebar, text="No lessons yet.", font=(FONT_BODY, 12, "italic"),
                         text_color=DIM).grid(row=0, column=0, pady=20, padx=12)
            ctk.CTkLabel(self._reading, text="Click 'Generate with agy' to get today's 10 lessons.",
                         font=(FONT_BODY, 14, "italic"), text_color=DIM).grid(row=0, column=0, pady=40)
            return

        row, last_date = 0, None
        for i, ch in enumerate(self._chapters):
            if ch["date"] != last_date:
                last_date = ch["date"]
                ctk.CTkLabel(self._sidebar, text=pretty_date(last_date), font=(FONT_BODY, 11, "bold"),
                             text_color=DIM, anchor="w").grid(
                    row=row, column=0, sticky="ew", padx=10, pady=(14 if row else 8, 4))
                row += 1
            self._chapter_row(i, ch).grid(row=row, column=0, sticky="ew", padx=6, pady=2)
            row += 1

        self._reading_pane(self._chapters[self._selected])

    def _chapter_row(self, idx, ch):
        active = idx == self._selected
        learned = ch["lesson"].get("learned", False)
        f = ctk.CTkFrame(self._sidebar, fg_color=BLUE_SOFT if active else "transparent",
                         corner_radius=8, cursor="hand2")
        f.grid_columnconfigure(1, weight=1)
        badge = ctk.CTkLabel(f, text="✓" if learned else str(idx + 1), font=(FONT_BODY, 11, "bold"),
                             width=22, text_color="#FFFFFF" if learned else (BLUE if active else DIM),
                             fg_color=GREEN if learned else "transparent", corner_radius=10)
        badge.grid(row=0, column=0, padx=(8, 6), pady=8)
        lbl = ctk.CTkLabel(f, text=ch["lesson"].get("title", ""), anchor="w", justify="left",
                           font=(FONT_BODY, 12, "bold" if active else "normal"),
                           text_color=BLUE if active else INK2, wraplength=170)
        lbl.grid(row=0, column=1, sticky="w", padx=(0, 8), pady=8)
        for w in (f, badge, lbl):
            w.bind("<Button-1>", lambda e, i=idx: self._select(i))
        return f

    def _reading_pane(self, ch):
        les, idx = ch["lesson"], self._selected
        learned = les.get("learned", False)

        ctk.CTkLabel(self._reading, text=f"CHAPTER {idx + 1} · {pretty_date(ch['date'])}",
                     font=(FONT_BODY, 11, "bold"), text_color=BLUE).grid(
            row=0, column=0, sticky="w", pady=(0, 4))
        ctk.CTkLabel(self._reading, text=les.get("title", ""), anchor="w", justify="left",
                     font=(FONT_HEAD, 24, "bold"), text_color=INK, wraplength=760).grid(
            row=1, column=0, sticky="w", pady=(2, 14))

        what = les.get("what", "")
        if what:
            ctk.CTkLabel(self._reading, text=what, anchor="w", justify="left", font=(FONT_BODY, 14),
                         text_color=INK2, wraplength=760).grid(row=2, column=0, sticky="w", pady=(0, 14))

        example = les.get("example", "")
        if example:
            ex = ctk.CTkFrame(self._reading, fg_color="#102036", corner_radius=10,
                              border_width=1, border_color="#1C2E47")
            ex.grid(row=3, column=0, sticky="ew", pady=(0, 14))
            ctk.CTkLabel(ex, text="EXAMPLE", font=(FONT_BODY, 10, "bold"),
                         text_color="#7FA8D9").grid(row=0, column=0, sticky="w", padx=16, pady=(12, 0))
            ctk.CTkLabel(ex, text=example, anchor="w", justify="left", font=("Cascadia Mono", 13),
                         text_color="#E8EEF7", wraplength=720).grid(
                row=1, column=0, sticky="w", padx=16, pady=(4, 14))

        action = les.get("action", "")
        if action:
            af = ctk.CTkFrame(self._reading, fg_color=YOLK_SOFT, corner_radius=8)
            af.grid(row=4, column=0, sticky="ew", pady=(0, 18))
            af.grid_columnconfigure(1, weight=1)
            ic = icon("check", "yolk", 15)
            if ic:
                ctk.CTkLabel(af, text="", image=ic).grid(row=0, column=0, padx=(12, 4), pady=10)
            ctk.CTkLabel(af, text=action, anchor="w", justify="left", font=(FONT_BODY, 13, "bold"),
                         text_color=YOLK_DK, wraplength=680).grid(
                row=0, column=1, padx=(0, 12), pady=10, sticky="w")

        btns = ctk.CTkFrame(self._reading, fg_color="transparent")
        btns.grid(row=5, column=0, sticky="ew", pady=(0, 8))
        ctk.CTkButton(btns, text="Learned" if learned else "Mark learned",
                      width=130, height=34, corner_radius=10,
                      fg_color=GREEN if learned else CARD2,
                      hover_color=GREEN_DK if learned else BLUE_SOFT,
                      text_color="#FFFFFF" if learned else INK2,
                      border_width=0 if learned else 1, border_color=BORDER,
                      font=(FONT_BODY, 12, "bold"),
                      image=icon("circle_check", "cream" if learned else "dim", 16), compound="left",
                      command=lambda: self._toggle(ch)).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Edit", width=90, height=34, corner_radius=10,
                      fg_color="transparent", hover_color=BLUE_SOFT, border_width=1, border_color=BORDER,
                      text_color=INK2, font=(FONT_BODY, 12, "bold"),
                      image=icon("edit", "dim", 16), compound="left",
                      command=lambda: self._edit(ch)).pack(side="left")

        nav = ctk.CTkFrame(self._reading, fg_color="transparent")
        nav.grid(row=6, column=0, sticky="ew", pady=(10, 4))
        nav.grid_columnconfigure(0, weight=1)
        nav.grid_columnconfigure(1, weight=1)
        prev_btn = ctk.CTkButton(nav, text="← Previous", width=140, height=38, corner_radius=10,
                      fg_color=CARD2, hover_color=BLUE_SOFT, text_color=INK2, font=(FONT_BODY, 12, "bold"))
        prev_btn.configure(command=(lambda: self._select(idx - 1)) if idx > 0 else None,
                           state="normal" if idx > 0 else "disabled")
        prev_btn.grid(row=0, column=0, sticky="w")
        next_btn = ctk.CTkButton(nav, text="Next →", width=140, height=38, corner_radius=10,
                      fg_color=BLUE, hover_color=BLUE_DK, text_color="#FFFFFF", font=(FONT_BODY, 12, "bold"))
        has_next = idx < len(self._chapters) - 1
        next_btn.configure(command=(lambda: self._select(idx + 1)) if has_next else None,
                           state="normal" if has_next else "disabled")
        next_btn.grid(row=0, column=1, sticky="e")


# ── Terminal Tab ───────────────────────────────────────────────────────────────

class TerminalTab(ctk.CTkFrame):
    POLL_MS = 50

    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self._pty = None
        self._proc = None          # subprocess.Popen fallback (frozen exe)
        self._pipe_mode = False    # try PTY first, fallback to pipe if it fails
        self._q = queue.Queue()
        self._running = False
        self._history = []
        self._hist_idx = -1
        self._cur_line = ""
        self._has_live = False
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()
        self.after(300, self._start_pty)

    def _build(self):
        hdr = TabHeader(self, "agy Terminal", "Live Gemini 3.5 Flash session", "terminal")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        self._status = ctk.CTkLabel(hdr.actions, text="Starting…", font=(FONT_BODY, 12, "bold"),
                                    text_color=DIM)
        self._status.grid(row=0, column=0, padx=10)
        pill_button(hdr.actions, "Restart", self._restart, "ghost", "refresh", "ink").grid(row=0, column=1, padx=4)
        pill_button(hdr.actions, "Clear", self._clear, "ghost", "x", "ink").grid(row=0, column=2, padx=4)

        wrap = ctk.CTkFrame(self, fg_color="#102036", corner_radius=14, border_width=1, border_color=BORDER)
        wrap.grid(row=1, column=0, sticky="nsew", padx=22, pady=(0, 8))
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        self._out = ctk.CTkTextbox(wrap, wrap="word", font=("Cascadia Mono", 13),
                                   text_color="#E8EEF7", fg_color="#102036",
                                   border_width=0, corner_radius=14,
                                   scrollbar_button_color="#2C456A")
        self._out.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, sticky="ew", padx=22, pady=(2, 16))
        row.grid_columnconfigure(0, weight=1)
        self._entry = ctk.CTkEntry(row, font=("Cascadia Mono", 13), fg_color=CARD,
                                   border_color=BLUE, text_color=INK,
                                   placeholder_text="Type a command and press Enter…",
                                   height=44, corner_radius=12)
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self._entry.bind("<Return>", self._send)
        self._entry.bind("<Up>", self._hist_up)
        self._entry.bind("<Down>", self._hist_down)
        pill_button(row, "Send", self._send, "primary", "send", "cream", width=100).grid(row=0, column=1)

    _DEFAULT_CWD = str(Path.home())  # neutral location; works from any install dir

    def _default_args(self):
        exe = agy_exe()
        if exe.exists() or shutil.which(str(exe)) or shutil.which("agy"):
            model_id = agy_model()
            # Only pass --model if we have a valid-looking API identifier
            if model_id and "-" in model_id:
                return [str(exe), "--model", model_id]
            return [str(exe)]
        if os.name == 'nt':
            return ["cmd.exe"]
        else:
            return ["/bin/bash", "-i"]

    def _start_pty(self):
        self._start_pty_with(self._default_args(), self._DEFAULT_CWD)

    def _start_pty_with(self, args, cwd=None):
        cwd = cwd or str(Path.home())
        
        exe_path = args[0]
        is_fallback = ("cmd.exe" in exe_path or "bash" in exe_path or "sh" in exe_path)
        
        if not is_fallback:
            p = Path(exe_path)
            if not (p.exists() or shutil.which(exe_path) or shutil.which("agy")):
                self._append(f"⚠  agy CLI executable not found at: '{exe_path}'\n")
                self._append("Please install it or configure the path in the Settings tab.\n")
                self._append("Spawning fallback system shell...\n\n")
                args = ["cmd.exe"] if os.name == 'nt' else ["/bin/bash", "-i"]
                is_fallback = True

        # Frozen Exe Pipe Mode Fallback check
        if getattr(sys, 'frozen', False):
            self._running = True
            self._pipe_mode = True
            self._status.configure(text="● agy Connected", text_color=GREEN)
            self._append("agy terminal ready. Type a prompt and press Send.\n(Running in pipe mode)\n\n")
            self.after(self.POLL_MS, self._poll_queue)
            return

        try:
            import winpty
        except ImportError:
            self._append("⚠  winpty not installed. Run:  pip install pywinpty\n")
            self._status.configure(text="pywinpty missing", text_color=RED)
            return

        try:
            self._pty = winpty.PtyProcess.spawn(args, cwd=cwd, env=clean_env(), dimensions=(40, 220))
            self._running = True
            status_text = "● Shell Connected" if is_fallback else "● agy Connected"
            self._status.configure(text=status_text, text_color=GREEN)
            threading.Thread(target=self._reader, daemon=True).start()
            self.after(self.POLL_MS, self._poll_queue)
        except Exception as e:
            self._append(f"⚠  Failed to spawn process {args}: {e}\nFalling back to pipe mode...\n")
            self._pipe_mode = True
            self._pty = None
            self._running = True
            self._status.configure(text="● agy Connected", text_color=GREEN)
            self._append("agy terminal ready (pipe mode).\n\n")
            self.after(self.POLL_MS, self._poll_queue)

    def _run_pipe(self, prompt: str, display_text: str = None):
        exe = agy_exe()
        exe_str = str(exe) if exe.exists() else (shutil.which("agy") or "agy")
        cmd = [exe_str, "--print", prompt, "--dangerously-skip-permissions", "--sandbox"]
        model_id = agy_model()
        if model_id and "-" in model_id:
            cmd.extend(["--model", model_id])
            
        self._append(f"\n> {display_text or prompt}\n")
        self._status.configure(text="● Running...", text_color=YOLK_DK)

        def _stream():
            try:
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, env=clean_env(), cwd=str(Path.home()),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                for line in proc.stdout:
                    self._q.put(ANSI_RE.sub('', line))
                proc.wait()
            except Exception as ex:
                self._q.put(f"\n[pipe error: {ex}]\n")
            finally:
                self._q.put("\n")
                self.after(0, lambda: self._status.configure(
                    text="● agy Connected", text_color=GREEN))

        threading.Thread(target=_stream, daemon=True).start()
        self.after(self.POLL_MS, self._poll_queue)

    def send_prompt(self, text, display_text=None):
        if not self._running:
            self._append("\n[Terminal not connected — click Restart]\n")
            return
        if text.strip():
            self._history.insert(0, display_text or text); self._hist_idx = -1
        # Pipe mode (frozen exe): run agy --print
        if self._pipe_mode:
            self._run_pipe(text, display_text)
            return
        # PTY mode
        if not self._pty:
            self._append("\n[Terminal not connected — click Restart]\n")
            return
        
        if display_text:
            self._append(f"\n> {display_text}\n")

        try:
            self._pty.write(text + "\r")
        except Exception as e:
            self._append(f"\n[send error: {e}]\n")

    def restart_with_args(self, args, cwd=None):
        self._running = False
        if self._pty:
            try: self._pty.terminate()
            except Exception: pass
            self._pty = None
        self._clear()
        self._status.configure(text="Connecting…", text_color=YOLK_DK)
        self.after(600, lambda: self._start_pty_with(args, cwd))

    def _restart(self):
        self.restart_with_args(self._default_args(), self._DEFAULT_CWD)

    def _reader(self):
        """Background thread: read PTY output and push into queue.
        Empty reads are normal during agy startup — we allow up to 120
        consecutive empty reads (~6 s at 50 ms poll) before concluding the
        session has truly ended.
        """
        empty_streak = 0
        MAX_EMPTY = 120  # ~6 seconds of silence before giving up
        while self._running:
            try:
                chunk = self._pty.read(4096)
                if chunk:
                    self._q.put(chunk)
                    empty_streak = 0  # reset on any real output
                else:
                    empty_streak += 1
                    if empty_streak > MAX_EMPTY:
                        break  # process truly gone
                    import time; time.sleep(0.05)  # wait 50 ms and retry
            except Exception as e:
                # Show the real error so we can diagnose PTY failures
                self._q.put(f"\n[PTY error: {type(e).__name__}: {e}]\n")
                break
        self._running = False
        self._q.put("\n[agy session ended — click Restart]\n")

    def _poll_queue(self):
        raw = ""
        try:
            while True:
                raw += self._q.get_nowait()
        except queue.Empty:
            pass
        if raw:
            self._process(ANSI_RE.sub('', raw))
        if self._running or not self._q.empty():
            self.after(self.POLL_MS, self._poll_queue)
        else:
            self._status.configure(text="● Disconnected", text_color=DIM)

    def _tw(self):
        return self._out._textbox

    def _process(self, raw):
        tw = self._tw(); tw.configure(state="normal")
        i = 0
        while i < len(raw):
            ch = raw[i]
            if ch == '\r' and i + 1 < len(raw) and raw[i + 1] == '\n':
                self._commit(tw); i += 2
            elif ch == '\n':
                self._commit(tw); i += 1
            elif ch == '\r':
                self._cur_line = ""; i += 1
            else:
                j = i + 1
                while j < len(raw) and raw[j] not in ('\r', '\n'):
                    j += 1
                self._cur_line += raw[i:j]; i = j
        self._draw_live(tw)

    def _commit(self, tw):
        if self._has_live:
            try: tw.delete("LIVE", "end-1c")
            except Exception: pass
            self._has_live = False
        tw.insert("end-1c", self._cur_line + "\n")
        tw.see("end"); self._cur_line = ""

    def _draw_live(self, tw):
        if not self._cur_line:
            if self._has_live:
                try: tw.delete("LIVE", "end-1c")
                except Exception: pass
                self._has_live = False
            return
        if self._has_live:
            try: tw.delete("LIVE", "end-1c")
            except Exception: self._has_live = False
        if not self._has_live:
            tw.mark_set("LIVE", "end-1c"); tw.mark_gravity("LIVE", "left")
            self._has_live = True
        tw.insert("end-1c", self._cur_line); tw.see("end")

    def _send(self, event=None):
        text = self._entry.get(); self._entry.delete(0, "end")
        if not text.strip():
            return
        if self._pipe_mode and self._running:
            self._history.insert(0, text); self._hist_idx = -1
            self._run_pipe(text)
            return
        if not self._pty or not self._running:
            return
        if text.strip():
            self._history.insert(0, text); self._hist_idx = -1
        try:
            self._pty.write(text + "\r")
        except Exception as e:
            self._append(f"\n[send error: {e}]\n")

    def _hist_up(self, event=None):
        if not self._history: return
        self._hist_idx = min(self._hist_idx + 1, len(self._history) - 1)
        self._entry.delete(0, "end"); self._entry.insert(0, self._history[self._hist_idx])

    def _hist_down(self, event=None):
        if self._hist_idx <= 0:
            self._hist_idx = -1; self._entry.delete(0, "end"); return
        self._hist_idx -= 1
        self._entry.delete(0, "end"); self._entry.insert(0, self._history[self._hist_idx])

    def _append(self, text):
        tw = self._tw(); tw.configure(state="normal")
        if self._has_live:
            try: tw.delete("LIVE", "end-1c")
            except Exception: pass
            self._has_live = False
        tw.insert("end-1c", text); tw.see("end")

    def _clear(self):
        tw = self._tw(); tw.configure(state="normal")
        tw.delete("1.0", "end-1c"); self._cur_line = ""; self._has_live = False

    def _restart(self):
        self.restart_with_args(self._default_args(), self._DEFAULT_CWD)

    def destroy(self):
        self._running = False
        if self._pty:
            try: self._pty.terminate()
            except Exception: pass
        super().destroy()


# ── Settings Tab ───────────────────────────────────────────────────────────────

FONT_FACES = ["Segoe UI", "Calibri", "Georgia", "Verdana", "Trebuchet MS", "Tahoma", "Cambria"]

class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, on_save=None):
        super().__init__(parent, fg_color="transparent")
        self._on_save = on_save
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        hdr = TabHeader(self, "Settings", "Fonts & AI prompt instructions", "settings")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=18, pady=4)
        self._scroll.grid_columnconfigure(0, weight=1)
        self._build_body()

    def _section(self, title, row):
        ctk.CTkLabel(self._scroll, text=title, font=(FONT_HEAD, 17, "bold"),
                     text_color=BLUE).grid(row=row, column=0, sticky="w", pady=(20, 8))
        return row + 1

    def _build_body(self):
        s = self._scroll
        r = self._section("Display", 0)

        th = card_frame(s); th.grid(row=r, column=0, sticky="ew", pady=4)
        th.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(th, text="Theme", font=(FONT_BODY, 14), text_color=INK).grid(
            row=0, column=0, padx=16, pady=14, sticky="w")
        self._theme_var = ctk.StringVar(value=SETTINGS.get("theme", "light"))
        ctk.CTkOptionMenu(th, variable=self._theme_var, values=["light", "dark"],
                          width=160, height=36, font=(FONT_BODY, 13),
                          fg_color=BLUE_SOFT, button_color=BLUE, button_hover_color=BLUE_DK,
                          text_color=INK, dropdown_fg_color=CARD,
                          dropdown_text_color=INK).grid(row=0, column=2, padx=16, pady=14)
        ctk.CTkLabel(th, text="Restart app to apply", font=(FONT_BODY, 11),
                     text_color=DIM).grid(row=0, column=3, padx=(0, 16), pady=14, sticky="w")
        r += 1

        fs = card_frame(s); fs.grid(row=r, column=0, sticky="ew", pady=4)
        fs.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(fs, text="Content font size (px)", font=(FONT_BODY, 14),
                     text_color=INK).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        self._fs_var = ctk.StringVar(value=str(SETTINGS.get("font_size", 16)))
        ctk.CTkEntry(fs, textvariable=self._fs_var, width=90, height=36, font=("Consolas", 14),
                     fg_color=CARD2, border_color=BORDER, text_color=INK).grid(
            row=0, column=2, padx=16, pady=14)
        r += 1

        ff = card_frame(s); ff.grid(row=r, column=0, sticky="ew", pady=4)
        ff.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ff, text="Content font face", font=(FONT_BODY, 14),
                     text_color=INK).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        self._ff_var = ctk.StringVar(value=SETTINGS.get("font_face", "Segoe UI"))
        ctk.CTkOptionMenu(ff, variable=self._ff_var, values=FONT_FACES, width=230, height=36,
                          font=(FONT_BODY, 13), fg_color=BLUE_SOFT, button_color=BLUE,
                          button_hover_color=BLUE_DK, text_color=INK,
                          dropdown_fg_color=CARD, dropdown_text_color=INK).grid(
            row=0, column=2, padx=16, pady=14)
        r += 1

        r = self._section("agy", r)

        ap = card_frame(s); ap.grid(row=r, column=0, sticky="ew", pady=4)
        ap.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ap, text="agy executable path", font=(FONT_BODY, 14),
                     text_color=INK).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        self._agy_var = ctk.StringVar(value=SETTINGS.get("agy_path", _detect_agy()))
        ctk.CTkEntry(ap, textvariable=self._agy_var, height=36, font=("Consolas", 12),
                     fg_color=CARD2, border_color=BORDER, text_color=INK).grid(
            row=0, column=1, padx=(16, 8), pady=14, sticky="ew")
        pill_button(ap, "Auto-Detect", self._auto_detect_agy, "primary", width=120).grid(
            row=0, column=2, padx=(0, 16), pady=14)
        r += 1

        mr = card_frame(s); mr.grid(row=r, column=0, sticky="ew", pady=4)
        mr.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(mr, text="Model", font=(FONT_BODY, 14),
                     text_color=INK).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        self._model_var = ctk.StringVar(value=SETTINGS.get("model", "gemini-3.5-flash-medium"))
        models = [
            "Gemini 3.5 Flash (Low)",
            "Gemini 3.5 Flash (Medium)",
            "Gemini 3.5 Flash (High)",
            "Gemini 3.1 Pro (Low)",
            "Gemini 3.1 Pro (High)"
        ]
        ctk.CTkOptionMenu(mr, variable=self._model_var, values=models, width=260, height=36,
                          font=(FONT_BODY, 13), fg_color=BLUE_SOFT, button_color=BLUE,
                          button_hover_color=BLUE_DK, text_color=INK,
                          dropdown_fg_color=CARD, dropdown_text_color=INK).grid(
            row=0, column=2, padx=16, pady=14)
        r += 1

        ag = card_frame(s); ag.grid(row=r, column=0, sticky="ew", pady=4)
        ag.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(ag, text="Auto-generate missing content on launch", font=(FONT_BODY, 14),
                     text_color=INK).grid(row=0, column=0, padx=16, pady=14, sticky="w")
        self._auto_var = ctk.BooleanVar(value=bool(SETTINGS.get("auto_generate", True)))
        ctk.CTkSwitch(ag, text="", variable=self._auto_var, onvalue=True, offvalue=False,
                      progress_color=GREEN, button_color=CARD, fg_color=BG2).grid(
            row=0, column=2, padx=16, pady=14)
        r += 1

        # Section: Blogging & Publishing
        r = self._section("Blogging & Publishing", r)

        wp = card_frame(s); wp.grid(row=r, column=0, sticky="ew", pady=4)
        wp.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(wp, text="WordPress URL", font=(FONT_BODY, 14), text_color=INK).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self._wp_url_var = ctk.StringVar(value=SETTINGS.get("wp_url", "https://yourblog.com"))
        ctk.CTkEntry(wp, textvariable=self._wp_url_var, height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=0, column=1, padx=16, pady=10, sticky="ew")
        
        ctk.CTkLabel(wp, text="WP Username", font=(FONT_BODY, 14), text_color=INK).grid(row=1, column=0, padx=16, pady=10, sticky="w")
        self._wp_user_var = ctk.StringVar(value=SETTINGS.get("wp_username", "admin"))
        ctk.CTkEntry(wp, textvariable=self._wp_user_var, height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=1, column=1, padx=16, pady=10, sticky="ew")

        ctk.CTkLabel(wp, text="WP Application Password", font=(FONT_BODY, 14), text_color=INK).grid(row=2, column=0, padx=16, pady=10, sticky="w")
        self._wp_pass_var = ctk.StringVar(value=SETTINGS.get("wp_app_password", ""))
        ctk.CTkEntry(wp, textvariable=self._wp_pass_var, show="*", height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=2, column=1, padx=16, pady=10, sticky="ew")
        r += 1

        gh = card_frame(s); gh.grid(row=r, column=0, sticky="ew", pady=4)
        gh.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(gh, text="Ghost URL", font=(FONT_BODY, 14), text_color=INK).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self._ghost_url_var = ctk.StringVar(value=SETTINGS.get("ghost_url", "https://yourblog.ghost.io"))
        ctk.CTkEntry(gh, textvariable=self._ghost_url_var, height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=0, column=1, padx=16, pady=10, sticky="ew")
        
        ctk.CTkLabel(gh, text="Ghost Admin API Key", font=(FONT_BODY, 14), text_color=INK).grid(row=1, column=0, padx=16, pady=10, sticky="w")
        self._ghost_key_var = ctk.StringVar(value=SETTINGS.get("ghost_admin_api_key", ""))
        ctk.CTkEntry(gh, textvariable=self._ghost_key_var, show="*", height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=1, column=1, padx=16, pady=10, sticky="ew")
        r += 1

        gt = card_frame(s); gt.grid(row=r, column=0, sticky="ew", pady=4)
        gt.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(gt, text="Git Repo Root Path (for MDX)", font=(FONT_BODY, 14), text_color=INK).grid(row=0, column=0, padx=16, pady=10, sticky="w")
        self._git_path_var = ctk.StringVar(value=SETTINGS.get("git_repo_path", ""))
        ctk.CTkEntry(gt, textvariable=self._git_path_var, height=36, font=(FONT_BODY, 13), fg_color=CARD2, border_color=BORDER, text_color=INK).grid(row=0, column=1, padx=16, pady=10, sticky="ew")
        r += 1

        r = self._section("AI Prompt Instructions", r)
        ctk.CTkLabel(s, text="Sent to the terminal when you click the 'agy' button on each tab. "
                            "The app appends the exact target file path automatically.",
                     font=(FONT_BODY, 12), text_color=DIM).grid(row=r, column=0, sticky="w", pady=(0, 6))
        r += 1

        self._boxes = {}
        for label, key in [
            ("Top Picks instruction", "top_picks_instruction"),
            ("Plan instruction (writes plan.json)", "plan_instruction"),
            ("Activities instruction (writes activities.json)", "activities_instruction"),
            ("Lessons instruction (writes lessons.json)", "lessons_instruction"),
        ]:
            ctk.CTkLabel(s, text=label, font=(FONT_BODY, 14, "bold"),
                         text_color=INK).grid(row=r, column=0, sticky="w", pady=(14, 3)); r += 1
            box = ctk.CTkTextbox(s, height=130, wrap="word", font=(FONT_BODY, 12),
                                 fg_color=CARD, text_color=INK, border_color=BORDER,
                                 border_width=1, corner_radius=10)
            box.grid(row=r, column=0, sticky="ew", pady=(0, 4))
            box.insert("1.0", SETTINGS.get(key, ""))
            self._boxes[key] = box; r += 1

        sf = ctk.CTkFrame(s, fg_color="transparent")
        sf.grid(row=r, column=0, sticky="ew", pady=(20, 28))
        self._save_btn = pill_button(sf, "Save Settings", self._save, "accent", "check", "ink", width=200)
        self._save_btn.pack(side="left", padx=4)
        self._save_lbl = ctk.CTkLabel(sf, text="", font=(FONT_BODY, 13), text_color=GREEN)
        self._save_lbl.pack(side="left", padx=12)

    def _auto_detect_agy(self):
        detected = _detect_agy()
        p = Path(detected)
        if p.exists() or shutil.which(detected) or shutil.which("agy"):
            self._agy_var.set(detected)
            if APP:
                APP.toast("agy.exe auto-detected successfully!", "ok")
        else:
            self._agy_var.set(detected)
            if APP:
                APP.toast("agy not found. Please set path manually.", "error")

    def _save(self):
        try:
            fs = max(10, min(int(self._fs_var.get()), 32))
        except ValueError:
            fs = 16
        new_s = {
            "font_size": fs,
            "font_face": self._ff_var.get(),
            "theme": self._theme_var.get(),
            "agy_path": self._agy_var.get().strip(),
            "model": self._model_var.get(),
            "auto_generate": bool(self._auto_var.get()),
            "wp_url": self._wp_url_var.get().strip(),
            "wp_username": self._wp_user_var.get().strip(),
            "wp_app_password": self._wp_pass_var.get().strip(),
            "ghost_url": self._ghost_url_var.get().strip(),
            "ghost_admin_api_key": self._ghost_key_var.get().strip(),
            "git_repo_path": self._git_path_var.get().strip(),
        }
        for k, box in self._boxes.items():
            new_s[k] = box.get("1.0", "end").strip()
        save_settings(new_s)
        self._save_btn.configure(text="  Saved!")
        self._save_lbl.configure(text="Top Picks re-rendered with new font.")
        self.after(2500, lambda: (self._save_btn.configure(text="  Save Settings"),
                                  self._save_lbl.configure(text="")))
        if self._on_save:
            self._on_save()


# ── Trends Tab ────────────────────────────────────────────────────────────────

class TrendsTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color="transparent")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self._build()

    def _build(self):
        hdr = TabHeader(self, "Trends", "7-day completion history", "trending")
        hdr.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 8))
        pill_button(hdr.actions, "Refresh", self.refresh, "ghost", "refresh", "ink").grid(row=0, column=0, padx=4)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self._scroll.grid_columnconfigure(0, weight=1)

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()
        dates = sorted(list_history_dates())[-14:]
        if not dates:
            ctk.CTkLabel(self._scroll, text="No history yet. Use MAYA for a few days to see trends.",
                         font=(FONT_BODY, 13, "italic"), text_color=DIM).grid(row=0, column=0, pady=30)
            return
        plan_pcts, act_done_counts, les_counts, labels = [], [], [], []
        for d in dates:
            pd = load_json(path_for("plan", d), {})
            tasks = [t for s in pd.get("sections", []) for t in s.get("tasks", [])]
            tot = len(tasks); dn = sum(1 for t in tasks if t.get("done"))
            plan_pcts.append(int(dn / tot * 100) if tot else 0)
            ad = load_json(path_for("activities", d), {})
            act_done_counts.append(sum(1 for t in ad.get("tasks", []) if t.get("status") == "done"))
            ld = load_json(path_for("lessons", d), {})
            les_counts.append(sum(1 for l in ld.get("lessons", []) if l.get("learned")))
            labels.append(d[5:])
        row = 0
        specs = [
            ("Plan Completion %", plan_pcts, YOLK, 100),
            ("Activities Completed", act_done_counts, GREEN, max(act_done_counts or [1], default=1)),
            ("Lessons Learned", les_counts, BLUE, max(les_counts or [1], default=1)),
        ]
        for title, vals, color, max_v in specs:
            c = card_frame(self._scroll)
            c.grid(row=row, column=0, sticky="ew", pady=8, padx=2)
            c.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(c, text=title, font=(FONT_HEAD, 15, "bold"),
                         text_color=INK, anchor="w").grid(row=0, column=0, padx=18, pady=(14, 6), sticky="w")
            self._bar_chart(c, labels, vals, color, max_v).grid(
                row=1, column=0, sticky="ew", padx=18, pady=(0, 14))
            row += 1

    def _bar_chart(self, parent, labels, values, bar_color, max_v):
        import tkinter as tk
        n = max(len(labels), 1)
        W, H = 860, 130
        pl, pr, pb, pt = 8, 8, 28, 12
        avail_w = W - pl - pr
        avail_h = H - pt - pb
        slot = avail_w // n
        bw = max(6, int(slot * 0.6))
        cv = tk.Canvas(parent, width=W, height=H, bg=CARD, highlightthickness=0)
        for i, (lbl, val) in enumerate(zip(labels, values)):
            cx = pl + i * slot + slot // 2
            bar_h = int(val / max(max_v, 1) * avail_h)
            y0 = pt + avail_h - bar_h
            y1 = pt + avail_h
            cv.create_rectangle(cx - bw // 2, y0, cx + bw // 2, y1,
                                 fill=bar_color, outline="", width=0)
            cv.create_text(cx, H - 2, text=lbl, font=("Segoe UI", 8),
                           fill=DIM, anchor="s")
            if val > 0:
                cv.create_text(cx, max(y0 - 2, pt), text=str(val),
                               font=("Segoe UI", 8, "bold"), fill=INK, anchor="s")
        return cv


# ── Global Search Panel ────────────────────────────────────────────────────────

class GlobalSearchPanel(ctk.CTkFrame):
    def __init__(self, parent, jump_fn):
        super().__init__(parent, fg_color=CARD, corner_radius=14,
                         border_width=1, border_color=BORDER, width=500)
        self._jump = jump_fn
        self.grid_columnconfigure(0, weight=1)
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", height=220)
        self._scroll.grid_columnconfigure(0, weight=1)

    def search(self, query: str, ds: str):
        q = query.strip().lower()
        if not q:
            self.place_forget(); return
        results = []
        plan = load_json(path_for("plan", ds), {})
        for s in plan.get("sections", []):
            for t in s.get("tasks", []):
                if q in t.get("title", "").lower():
                    results.append((2, "Plan", t["title"]))
        act = load_json(path_for("activities", ds), {})
        for t in act.get("tasks", []):
            if q in (t.get("title", "") + t.get("note", "")).lower():
                results.append((1, "Activities", t["title"]))
        les = load_json(path_for("lessons", ds), {})
        for l in les.get("lessons", []):
            if q in (l.get("title", "") + l.get("what", "")).lower():
                results.append((3, "Lessons", l["title"]))
        tp = path_for("top_picks", ds)
        if tp.exists():
            for line in tp.read_text(encoding="utf-8", errors="replace").splitlines():
                if q in line.lower() and line.strip():
                    results.append((0, "Top Picks", line.strip()[:80]))
                    break
        for w in self._scroll.winfo_children():
            w.destroy()
        if not results:
            ctk.CTkLabel(self._scroll, text="No matches.", font=(FONT_BODY, 13, "italic"),
                         text_color=DIM).grid(row=0, column=0, pady=12, padx=16, sticky="w")
        else:
            for i, (tab_idx, tab_name, text) in enumerate(results[:12]):
                row = ctk.CTkFrame(self._scroll, fg_color=BG2, corner_radius=8)
                row.grid(row=i, column=0, sticky="ew", pady=3, padx=6)
                row.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(row, text=tab_name, font=(FONT_BODY, 11, "bold"),
                             fg_color=BLUE_SOFT, text_color=BLUE, corner_radius=6,
                             width=82).grid(row=0, column=0, padx=(8, 10), pady=7)
                ctk.CTkLabel(row, text=text, font=(FONT_BODY, 13), text_color=INK,
                             anchor="w").grid(row=0, column=1, sticky="w", padx=(0, 8))
                for w in (row, *row.winfo_children()):
                    w.bind("<Button-1>", lambda e, idx=tab_idx: (self.place_forget(), self._jump(idx)))
        self._scroll.grid(row=0, column=0, sticky="ew", padx=4, pady=6)
        self.place(relx=0.98, rely=0.06, anchor="ne")

    def hide(self):
        self.place_forget()


# ── Sidebar ────────────────────────────────────────────────────────────────────

NAV_ITEMS = [
    ("top_picks", "Top Picks"),
    ("research", "Research"),
    ("activities", "Activities"),
    ("plan", "Plan"),
    ("lessons", "Lessons"),
    ("trending", "Trends"),
    ("terminal", "Terminal"),
    ("settings", "Settings"),
]

class Sidebar(ctk.CTkFrame):
    def __init__(self, parent, on_select, on_refresh=None):
        super().__init__(parent, fg_color=CARD, corner_radius=0, width=236)
        self.grid_propagate(False)
        self._on_select = on_select
        self._on_refresh = on_refresh
        self._btns = []
        self._active = 0
        self._build()

    def _build(self):
        logo = ctk.CTkFrame(self, fg_color="transparent", cursor="hand2")
        logo.grid(row=0, column=0, sticky="ew", pady=(24, 6), padx=6)
        badge = ctk.CTkFrame(logo, fg_color=YOLK, corner_radius=12, width=44, height=44, cursor="hand2")
        badge.grid(row=0, column=0, padx=(12, 10)); badge.grid_propagate(False)
        badge_lbl = ctk.CTkLabel(badge, text="M", font=(FONT_HEAD, 22, "bold"),
                     text_color=INK, cursor="hand2")
        badge_lbl.place(relx=0.5, rely=0.5, anchor="center")
        name_lbl = ctk.CTkLabel(logo, text="MAYA", font=(FONT_HEAD, 24, "bold"),
                     text_color=INK, cursor="hand2")
        name_lbl.grid(row=0, column=1, sticky="w")
        if self._on_refresh:
            for w in (logo, badge, badge_lbl, name_lbl):
                w.bind("<Button-1>", lambda e: self._on_refresh())

        ctk.CTkFrame(self, fg_color=BORDER, height=1).grid(row=1, column=0, sticky="ew", padx=16, pady=14)
        ctk.CTkLabel(self, text="WORKSPACE", font=(FONT_BODY, 10, "bold"),
                     text_color=DIM).grid(row=2, column=0, sticky="w", padx=20, pady=(0, 8))

        for i, (ic, label) in enumerate(NAV_ITEMS):
            b = ctk.CTkButton(
                self, text="   " + label, anchor="w", height=50, width=208,
                font=(FONT_BODY, 15, "bold"), corner_radius=12,
                fg_color="transparent", hover_color=BG2, text_color=INK2,
                image=icon(ic, "blue", 22), compound="left",
                command=lambda idx=i: self.select(idx))
            b.grid(row=3 + i, column=0, padx=14, pady=3, sticky="ew")
            self._btns.append((b, ic, label))

        self.grid_rowconfigure(99, weight=1)
        ctk.CTkLabel(self, text=f"agy · {TODAY}", font=(FONT_BODY, 10),
                     text_color=DIM).grid(row=100, column=0, pady=14)
        self.select(0)

    def select(self, idx):
        self._active = idx
        for i, (b, ic, label) in enumerate(self._btns):
            active = (i == idx)
            b.configure(
                fg_color=BLUE if active else "transparent",
                hover_color=BLUE_DK if active else BG2,
                text_color="#FFFFFF" if active else INK2,
                image=icon(ic, "cream" if active else "blue", 22))
        self._on_select(idx)


# ── Status bar ─────────────────────────────────────────────────────────────────

class StatusBar(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent, fg_color=CARD, corner_radius=0, height=38, border_width=1, border_color=BORDER)
        self.grid_columnconfigure(1, weight=1)
        ok = agy_exe().exists() or shutil.which("agy")
        ctk.CTkLabel(self, text=("●  agy connected" if ok else "●  agy not found"),
                     font=(FONT_BODY, 12, "bold"), text_color=GREEN if ok else RED).grid(
            row=0, column=0, padx=16, pady=8, sticky="w")
        ctk.CTkLabel(self, text=f"content · {CONTENT_DIR}", font=(FONT_BODY, 12),
                     text_color=DIM).grid(row=0, column=1, padx=12, sticky="w")
        
        # Version and Update Check Label
        self._ver_lbl = ctk.CTkLabel(self, text="v1.0.0", font=(FONT_BODY, 12), text_color=DIM, cursor="hand2")
        self._ver_lbl.grid(row=0, column=2, padx=12, sticky="e")
        self._ver_lbl.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/Mdfar/mayadashboard/releases"))
        
        self._clock = ctk.CTkLabel(self, text="", font=(FONT_BODY, 12), text_color=INK2)
        self._clock.grid(row=0, column=3, padx=16, sticky="e")
        self._tick()
        
        # Run background check for update
        import threading
        threading.Thread(target=self._check_update, daemon=True).start()

    def _check_update(self):
        import requests
        try:
            res = requests.get("https://automationfunda.com/app-metadata.json", timeout=5)
            if res.status_code == 200:
                data = res.json()
                latest = data.get("version", "v1.0.0")
                if latest != "v1.0.0":
                    self.after(0, lambda: self._ver_lbl.configure(
                        text=f"● Update Available ({latest})",
                        text_color=BLUE,
                        font=(FONT_BODY, 12, "bold")
                    ))
        except Exception:
            pass

    def _tick(self):
        self._clock.configure(text=datetime.now().strftime("%A, %B %d  ·  %H:%M:%S"))
        self.after(1000, self._tick)


# ── Carry-over (unfinished tasks roll into a new day) ─────────────────────────

def carry_over(ds: str):
    prior = [d for d in list_history_dates() if d < ds]
    if not prior:
        return
    src = prior[0]
    pj = path_for("plan", ds)
    if not pj.exists():
        ok, fixed, _ = validate_and_fix("plan", load_json(path_for("plan", src), None))
        if ok and fixed:
            for s in fixed.get("sections", []):
                s["tasks"] = [t for t in s.get("tasks", []) if not t.get("done")]
            fixed["date"] = pretty_date(ds)
            save_json(pj, fixed)
    aj = path_for("activities", ds)
    if not aj.exists():
        ok, fixed, _ = validate_and_fix("activities", load_json(path_for("activities", src), None))
        if ok and fixed:
            fixed["tasks"] = [t for t in fixed.get("tasks", [])
                              if t.get("status") in ("active", "pending", "blocked")]
            fixed["recommendations"] = []
            save_json(aj, fixed)


# ── Date nav bar ───────────────────────────────────────────────────────────────

class DateBar(ctk.CTkFrame):
    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self._app = app
        ctk.CTkButton(self, text="◀", width=40, height=34, corner_radius=9,
                      font=(FONT_BODY, 14, "bold"), fg_color=CARD, hover_color=BG2,
                      text_color=INK, border_width=1, border_color=BORDER,
                      command=lambda: app.shift_date(-1)).pack(side="left", padx=(0, 6))
        self._lbl = ctk.CTkLabel(self, text="", font=(FONT_HEAD, 15, "bold"),
                                 text_color=INK, width=190)
        self._lbl.pack(side="left", padx=2)
        ctk.CTkButton(self, text="▶", width=40, height=34, corner_radius=9,
                      font=(FONT_BODY, 14, "bold"), fg_color=CARD, hover_color=BG2,
                      text_color=INK, border_width=1, border_color=BORDER,
                      command=lambda: app.shift_date(1)).pack(side="left", padx=6)
        self._today_btn = pill_button(self, "Today", lambda: app.goto_date(today_str()),
                                      "accent", "calendar-check" and "plan", "ink", width=96)
        self._today_btn.pack(side="left", padx=8)

    def set(self, ds: str):
        label = pretty_date(ds)
        if ds == today_str():
            label += "  · Today"
        self._lbl.configure(text=label)


# ── Main App ───────────────────────────────────────────────────────────────────

class DashboardApp(ctk.CTk):
    def __init__(self):
        global APP
        APP = self
        super().__init__()
        self.current_date = today_str()
        self._toast = None
        self._jobs = []
        carry_over(self.current_date)
        self.title(APP_TITLE)
        self.geometry(WIN_SIZE)
        self.minsize(1080, 680)
        self.configure(fg_color=BG)
        
        # Set Window Icon
        if os.name == 'nt':
            import ctypes
            try:
                # Register process with Windows shell to force taskbar icon refresh
                myappid = "mdfar.mayadashboard.workspace.1.0.1"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            except Exception:
                pass
            
            icon_path = BUNDLE_DIR / "assets" / "icon.ico"
            if icon_path.exists():
                try:
                    self.iconbitmap(str(icon_path))
                    self.wm_iconbitmap(str(icon_path))
                except Exception:
                    pass
        self._build_ui()
        self.after(2500, self._auto_generate)
        
        # Force window to foreground and focus on launch
        self.deiconify()
        self.lift()
        self.focus_force()
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))
        
        if HAS_INTEL:
            threading.Thread(target=start_background_poller, daemon=True).start()
            threading.Thread(target=write_context, daemon=True).start()

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._tabs = []  # must exist before Sidebar.select(0) fires _switch_tab
        self._sidebar = Sidebar(self, self._switch_tab, on_refresh=self._full_refresh)
        self._sidebar.grid(row=0, column=0, sticky="ns")

        content = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(1, weight=1)
        content.grid_columnconfigure(0, weight=1)

        topbar = ctk.CTkFrame(content, fg_color="transparent", height=52)
        topbar.grid(row=0, column=0, sticky="ew", padx=22, pady=(12, 0))
        topbar.grid_columnconfigure(1, weight=1)
        self._datebar = DateBar(topbar, self)
        self._datebar.grid(row=0, column=0, sticky="w")
        self._datebar.set(self.current_date)

        right_bar = ctk.CTkFrame(topbar, fg_color="transparent")
        right_bar.grid(row=0, column=2, sticky="e")
        self._search_var = ctk.StringVar()
        search_e = ctk.CTkEntry(right_bar, textvariable=self._search_var,
                                placeholder_text="Search…", width=200, height=36,
                                font=(FONT_BODY, 13), fg_color=CARD, border_color=BORDER,
                                text_color=INK, corner_radius=10)
        search_e.grid(row=0, column=0, padx=(0, 6))
        search_e.bind("<Return>", lambda e: self._do_search())
        search_e.bind("<Escape>", lambda e: (self._search_panel.hide(), self._search_var.set("")))
        pill_button(right_bar, "Export", self._export, "ghost", width=90).grid(row=0, column=1)

        holder = ctk.CTkFrame(content, fg_color="transparent")
        holder.grid(row=1, column=0, sticky="nsew")
        holder.grid_rowconfigure(0, weight=1)
        holder.grid_columnconfigure(0, weight=1)

        self._term = TerminalTab(holder)
        TERM_IDX = 6

        def ask_agy_fn(prompt):
            display = None
            if isinstance(prompt, tuple):
                prompt, display = prompt
                
            # Wait until the PTY is actually running before sending the prompt.
            # agy needs up to 2-3 s to start; 150 ms was far too short and
            # caused "send error: Pty is closed" every time.
            def _wait_and_send(remaining=40):  # 40 × 100 ms = 4 s max wait
                if self._term._running:
                    self._term.send_prompt(prompt, display)
                elif remaining > 0:
                    self.after(100, lambda: _wait_and_send(remaining - 1))
                else:
                    self._term._append("\n⚠  agy did not start in time. Click Restart and try again.\n")
            self.after(200, lambda: _wait_and_send())

        self._top     = TopPicksTab(holder, ask_agy_fn=ask_agy_fn)
        self._research = ResearchTab(holder, ask_agy_fn=ask_agy_fn)
        t_act         = ActivitiesTab(holder, ask_agy_fn=ask_agy_fn)
        t_plan        = PlanTab(holder, ask_agy_fn=ask_agy_fn)
        t_les         = LessonsTab(holder, ask_agy_fn=ask_agy_fn)
        self._trends  = TrendsTab(holder)
        t_set         = SettingsTab(holder, on_save=self._on_settings_save)

        self._tabs = [self._top, self._research, t_act, t_plan, t_les, self._trends, self._term, t_set]
        self._date_tabs = [self._top, self._research, t_act, t_plan, t_les]
        for tab in self._tabs:
            tab.grid(row=0, column=0, sticky="nsew")
            tab.grid_remove()
        # Sidebar.select(0) already fired _switch_tab(0) while self._tabs was
        # still empty (see comment above) — re-run now that tabs exist so the
        # active tab actually gets gridded visible on startup.
        self._switch_tab(self._sidebar._active)

        self._search_panel = GlobalSearchPanel(self, self._sidebar.select)
        StatusBar(self).grid(row=1, column=0, columnspan=2, sticky="ew")

    # ── full app refresh (reloads data/settings from disk in place, no restart) ──
    def _full_refresh(self):
        SETTINGS.clear()
        SETTINGS.update(load_settings())
        for tab in self._date_tabs:
            tab.on_date_change()
        self._trends.refresh()
        self.toast("MAYA refreshed", "ok")

    # ── toast ──
    def toast(self, msg, kind="info"):
        colors = {"info": (BLUE_SOFT, INK), "ok": (GREEN_SOFT, GREEN), "error": (RED_SOFT, RED)}
        bg, fg = colors.get(kind, colors["info"])
        if self._toast is not None:
            try: self._toast.destroy()
            except Exception: pass
        self._toast = ctk.CTkFrame(self, fg_color=bg, corner_radius=12,
                                   border_width=1, border_color=BORDER)
        ctk.CTkLabel(self._toast, text=msg, font=(FONT_BODY, 12, "bold"),
                     text_color=fg, wraplength=420).pack(padx=16, pady=10)
        self._toast.place(relx=0.985, rely=0.03, anchor="ne")
        t = self._toast
        self.after(4200, lambda: t.destroy() if t.winfo_exists() else None)

    # ── date nav ──
    def shift_date(self, delta):
        from datetime import timedelta
        d = datetime.strptime(self.current_date, "%Y-%m-%d") + timedelta(days=delta)
        self.goto_date(d.strftime("%Y-%m-%d"))

    def goto_date(self, ds):
        if ds == self.current_date:
            return
        self.current_date = ds
        if ds == today_str():
            carry_over(ds)
        self._datebar.set(ds)
        for tab in self._date_tabs:
            tab.on_date_change()

    # ── auto-generate ──
    def _auto_generate(self):
        if not SETTINGS.get("auto_generate", True):
            return
        if not (agy_exe().exists() or shutil.which("agy")):
            return
        ds = self.current_date
        jobs = []
        for kind, key in [("top_picks", "top_picks_instruction"), ("plan", "plan_instruction"),
                          ("lessons", "lessons_instruction"), ("activities", "activities_instruction")]:
            p = path_for(kind, ds)
            if (not p.exists()) or p.stat().st_size < 5:
                jobs.append((kind, key))
        if not jobs:
            return
        self._jobs = jobs
        self.toast("Auto-generating missing content with agy…", "info")
        self._run_next_job()

    def _run_next_job(self):
        if not self._jobs:
            self.toast("Auto-generation complete.", "ok")
            return
        kind, key = self._jobs[0]
        ds = self.current_date
        self._job_target = path_for(kind, ds)
        self._job_mtime0 = self._job_target.stat().st_mtime if self._job_target.exists() else 0.0
        self._job_deadline = time.time() + 180
        self._job_stable = None
        self._job_size = -1
        self._term.send_prompt(build_prompt(SETTINGS.get(key, ""), kind, ds))
        self.after(1500, self._watch_job)

    def _watch_job(self):
        tgt = self._job_target
        try:
            if tgt.exists():
                st = tgt.stat()
                if st.st_mtime != self._job_mtime0:
                    if st.st_size != self._job_size:
                        self._job_size = st.st_size
                        self._job_stable = time.time()
                    elif self._job_stable and (time.time() - self._job_stable) >= 2.5:
                        self._jobs.pop(0)
                        self.after(1200, self._run_next_job)
                        return
        except Exception:
            pass
        if time.time() > self._job_deadline:
            self._jobs.pop(0)
            self.after(500, self._run_next_job)
            return
        self.after(500, self._watch_job)

    def _do_search(self):
        q = self._search_var.get().strip()
        if not q:
            self._search_panel.hide(); return
        self._search_panel.search(q, self.current_date)

    def _export(self):
        try:
            out = export_content(self.current_date)
            self.toast(f"Exported → {out.name}", "ok")
            os.startfile(str(out))
        except Exception as e:
            self.toast(f"Export failed: {e}", "error")

    def _on_settings_save(self):
        self._top.rerender()

    def _switch_tab(self, idx):
        for i, tab in enumerate(self._tabs):
            (tab.grid() if i == idx else tab.grid_remove())
        if idx == 4:
            self._trends.refresh()


if __name__ == "__main__":
    # When frozen as a PyInstaller exe, write an env snapshot to a log file.
    # This lets us diagnose child-process environment issues without a debugger.
    if getattr(sys, 'frozen', False):
        try:
            log_dir = Path(os.environ.get("APPDATA", "~")).expanduser() / "MayaDashboard"
            log_dir.mkdir(parents=True, exist_ok=True)
            with open(log_dir / "startup_env.log", "w") as _f:
                _f.write(f"=== MayaDashboard frozen startup {datetime.now()} ===\n")
                _f.write(f"sys.frozen = {getattr(sys, 'frozen', False)}\n")
                _f.write(f"_MEIPASS   = {getattr(sys, '_MEIPASS', 'N/A')}\n\n")
                _f.write("--- Environment ---\n")
                for k, v in sorted(os.environ.items()):
                    _f.write(f"  {k}={v}\n")
                _f.write("\n--- clean_env() output ---\n")
                for k, v in sorted(clean_env().items()):
                    _f.write(f"  {k}={v}\n")
        except Exception:
            pass  # never crash startup over diagnostics

    app = DashboardApp()
    app.mainloop()
