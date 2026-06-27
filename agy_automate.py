#!/usr/bin/env python3
"""
agy_automate.py
Automates the agy CLI workflow from AGY_DASHBOARD_LIVE_WORKFLOW.md.
Opens agy, changes model to Gemini 3.5 Flash (Low), sends all 3 prompts
so dashboard auto-renders top_picks.md / plan.md / lessons.md.

No screenshots. All steps use clipboard paste (safe for paths) + AttachThreadInput
(reliable focus). Generous delays between each action.
"""

import subprocess, time, ctypes, sys
from pathlib import Path
import win32gui, win32process, win32clipboard
import pyautogui

# ── Config ─────────────────────────────────────────────────────────────────

AGY_EXE   = r"C:\Users\Mohammad Farhad\AppData\Local\agy\bin\agy.exe"
WORKSPACE = r"D:\AntigravityDashboard"
CONTENT   = "D:/AntigravityDashboard/content"   # forward slashes — no \t issue

# Max seconds to wait per prompt before giving up
FILE_TIMEOUT = 180

# Seconds file size must stay unchanged to be considered "write complete"
STABLE_SECS = 2.5

# Model passed directly as CLI flag — no /model menu needed.
# Options: "Gemini 3.5 Flash (Low)", "Gemini 3.5 Flash (Medium)", "Gemini 3.5 Flash (High)"
#          "Gemini 3.1 Pro (Low)", "Gemini 3.1 Pro (High)"
AGY_MODEL = "Gemini 3.5 Flash (Low)"

PROMPTS = {
    "top_picks": (
        "Research the 5 most important AI and tech developments for today. "
        f"Write raw HTML content directly to the file {CONTENT}/top_picks.md (overwrite it completely). "
        "Do not wrap in markdown backticks. For each pick, use exactly this HTML structure:\n"
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
        "</div>\n\n"
        "Do not explain, just write the file."
    ),
    "plan": (
        f"Write a practical daily plan for a software engineer and AI developer "
        f"to the file {CONTENT}/plan.md . "
        f"Use Morning / Afternoon / Evening sections with checkbox tasks. "
        f"Include a Top Priority section at the bottom. "
        f"Overwrite the file. Do not explain, just write the file."
    ),
    "lessons": (
        f"Write exactly 10 lessons for a software engineer working on AI "
        f"to the file {CONTENT}/lessons.md . "
        f"Each lesson: number + emoji title, What section (2-3 sentences), "
        f"Action section (1 concrete thing to do today). "
        f"Overwrite the file. Do not explain, just write the file."
    ),
}

# ── Helpers ─────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}".encode('ascii', errors='replace').decode(), flush=True)

def focus(hwnd: int):
    """Force keyboard focus to hwnd using AttachThreadInput."""
    cur = ctypes.windll.kernel32.GetCurrentThreadId()
    tgt = win32process.GetWindowThreadProcessId(hwnd)[0]
    ctypes.windll.user32.AttachThreadInput(cur, tgt, True)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    ctypes.windll.user32.BringWindowToTop(hwnd)
    time.sleep(0.5)
    ctypes.windll.user32.AttachThreadInput(cur, tgt, False)
    time.sleep(0.3)

def find_window(substr: str, timeout: int = 20) -> int:
    """Poll until visible window title contains substr. Returns HWND or exits."""
    log(f"Waiting for window: '{substr}' ...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        found = []
        def cb(h, _):
            if win32gui.IsWindowVisible(h) and substr.lower() in win32gui.GetWindowText(h).lower():
                found.append(h)
        win32gui.EnumWindows(cb, None)
        if found:
            log(f"Found HWND={found[0]}  title='{win32gui.GetWindowText(found[0])}'")
            return found[0]
        time.sleep(0.5)
    log(f"ERROR: window '{substr}' not found after {timeout}s")
    sys.exit(1)

def clip_paste_enter(hwnd: int, text: str):
    """
    Set clipboard to text, focus window, Ctrl+V, Enter.
    Safe for backslashes, emoji, and all special chars — avoids typewrite \t bug.
    """
    win32clipboard.OpenClipboard()
    win32clipboard.EmptyClipboard()
    win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
    win32clipboard.CloseClipboard()
    time.sleep(0.2)
    focus(hwnd)
    pyautogui.hotkey('ctrl', 'v')
    time.sleep(0.6)
    pyautogui.press('enter')
    time.sleep(0.5)

def key(hwnd: int, k: str, times: int = 1, delay: float = 0.2):
    focus(hwnd)
    for _ in range(times):
        pyautogui.press(k)
        time.sleep(delay)

def type_ascii(hwnd: int, text: str):
    """typewrite only for short ASCII with no special chars (e.g. /model)."""
    focus(hwnd)
    pyautogui.typewrite(text, interval=0.08)
    time.sleep(0.2)

# ── Steps ────────────────────────────────────────────────────────────────────

def launch_agy() -> int:
    log(f"Launching agy with model '{AGY_MODEL}' ...")
    subprocess.Popen(
        ['cmd.exe', '/k', AGY_EXE, '--model', AGY_MODEL],
        cwd=WORKSPACE,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
    )
    time.sleep(2)
    hwnd = find_window('agy', timeout=20)
    time.sleep(3)   # let agy fully render startup screen or trust prompt
    return hwnd

def handle_trust(hwnd: int):
    """
    Press Enter once.
    - If trust prompt shown → confirms 'Yes, I trust this folder'
    - If already trusted  → sends blank line (harmless in agy)
    """
    log("Sending Enter (handles trust prompt if shown) ...")
    key(hwnd, 'enter')
    time.sleep(4)   # wait for agy main screen


def wait_for_file(filepath: Path, before_mtime: float, timeout: int = FILE_TIMEOUT) -> bool:
    """
    Poll filepath until:
      1. mtime differs from before_mtime  — agy started writing
      2. file size unchanged for STABLE_SECS — write is complete
    Returns True on success, False on timeout.
    Prints a dot every 5s so the user sees it's still working.
    """
    deadline    = time.time() + timeout
    last_size   = -1
    stable_at   = None
    dot_at      = time.time() + 5

    while time.time() < deadline:
        if filepath.exists():
            st = filepath.stat()
            if st.st_mtime != before_mtime:          # file was touched
                if st.st_size != last_size:           # still writing
                    last_size = st.st_size
                    stable_at = time.time()
                elif stable_at and (time.time() - stable_at) >= STABLE_SECS:
                    return True                       # size stable — done
        if time.time() >= dot_at:
            print(".", end="", flush=True)
            dot_at = time.time() + 5
        time.sleep(0.4)

    print()   # newline after dots
    return False


def send_prompt(hwnd: int, name: str, prompt: str, filepath: Path):
    log(f"--- {name}: sending prompt ---")

    # Snapshot state before — so we detect any change after
    before_mtime = filepath.stat().st_mtime if filepath.exists() else 0.0

    clip_paste_enter(hwnd, prompt)
    log(f"Prompt sent. Watching {filepath.name} for changes (max {FILE_TIMEOUT}s) ...")

    done = wait_for_file(filepath, before_mtime)

    if done:
        log(f"{name}: file updated and stable — done")
    else:
        log(f"{name}: WARNING — timed out after {FILE_TIMEOUT}s, file may be incomplete")

    time.sleep(1.5)   # brief pause before next prompt so agy returns to prompt

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    content_dir = Path(CONTENT.replace("/", "\\"))
    content_dir.mkdir(parents=True, exist_ok=True)

    files = {
        "top_picks": content_dir / "top_picks.md",
        "plan":      content_dir / "plan.md",
        "lessons":   content_dir / "lessons.md",
    }

    hwnd = launch_agy()
    handle_trust(hwnd)

    send_prompt(hwnd, "top_picks", PROMPTS["top_picks"], files["top_picks"])
    send_prompt(hwnd, "plan",      PROMPTS["plan"],      files["plan"])
    send_prompt(hwnd, "lessons",   PROMPTS["lessons"],   files["lessons"])

    log("All done. Dashboard auto-renders as each file lands.")

if __name__ == "__main__":
    main()
