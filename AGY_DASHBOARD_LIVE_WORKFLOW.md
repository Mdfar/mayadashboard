# AGY → Dashboard Live Rendering Workflow
**Date:** June 16, 2026  
**Project:** `D:\AntigravityDashboard`  
**Goal:** Prove the full loop — agy writes a file → Python dashboard detects change → renders content in real-time, without any stdout capture

---

## Context

`agy.exe` (Antigravity CLI v1.0.8) writes output directly to the Windows console via Win32 API (`WriteConsole`), bypassing stdout entirely. Piping, `capture_output=True`, shell redirect (`>`), and PTY approaches (winpty) all return empty. The solution: **make agy write to files, watch files in the dashboard**.

---

## Architecture

```
┌─────────────────────┐        writes        ┌──────────────────────────────┐
│  agy (interactive   │ ──────────────────►  │  D:\AntigravityDashboard\    │
│  terminal session)  │  .md files           │  content\top_picks.md        │
│                     │                      │  content\plan.md             │
│  Model: Gemini 3.5  │                      │  content\lessons.md          │
│  Flash (Low)        │                      └──────────────────────────────┘
└─────────────────────┘                                      │
                                                    polls every 800ms
                                                             │
                                              ┌──────────────▼──────────────┐
                                              │  dashboard.py               │
                                              │  (CustomTkinter, Python)    │
                                              │  FileWatchTab._poll()       │
                                              │  → detects mtime change     │
                                              │  → set_text(textbox)        │
                                              │  → renders instantly        │
                                              └─────────────────────────────┘
```

---

## Step-by-Step Sequence

### Step 1 — Discover agy CLI Interface

**Observation:** `agy.exe` is at `C:\Users\Mohammad Farhad\AppData\Local\agy\bin\agy.exe` and is in system PATH.

**Command run:**
```bash
"C:/Users/Mohammad Farhad/AppData/Local/agy/bin/agy.exe" --help
```

**Key flags discovered:**
```
--print / -p      Run a single prompt non-interactively and print the response
--conversation    Resume a previous conversation by ID
--dangerously-skip-permissions   Auto-approve all tool permission requests
```

**Failed approach — stdout capture:**
```python
# ALL of these return empty output — agy uses Win32 WriteConsole, not stdout
subprocess.run([agy, "--print", "hello"], capture_output=True)   # stdout: ''
subprocess.Popen([agy, ...], stdout=PIPE)                        # readline: ''
winpty.PtyProcess.spawn([agy, ...])                              # chunks: []
shell redirect: agy --print "hello" > out.txt                    # file size: 0
```

**Root cause:** agy renders to the Windows console directly. No stdout when piped.

---

### Step 2 — Design File-Based Integration

**Decision:** agy has full filesystem access (it's an AI agent). Tell agy via natural language to **write output to a specific file path**. Dashboard watches that path.

**Content directory created:**
```
D:\AntigravityDashboard\content\
    top_picks.md    ← Tab 1: Top Picks Today
    plan.md         ← Tab 3: Today's Plan
    lessons.md      ← Tab 4: Today's 10 Lessons
```

**Dashboard file watcher (Python, polls every 800ms):**
```python
POLL_MS = 800

def _poll(self):
    if self._content_file.exists():
        stat = self._content_file.stat()
        if stat.st_mtime != self._last_mtime or stat.st_size != self._last_size:
            self._last_mtime = stat.st_mtime
            self._last_size  = stat.st_size
            self._reload()          # reads file → updates CTkTextbox instantly
    self.after(self.POLL_MS, self._poll)
```

---

### Step 3 — Launch Dashboard (Updated Code)

**Kill old dashboard process, launch new:**
```bash
# In PowerShell
Stop-Process -Name "pythonw" -Force -ErrorAction SilentlyContinue

# In Bash
cd "D:/AntigravityDashboard" && start pythonw dashboard.py
```

**Bug encountered:** `AttributeError: '_tkinter.tkapp' object has no attribute '_tabs'`  
**Cause:** `Sidebar.__init__` called `select(0)` → `_switch_tab(0)` → referenced `self._tabs` before it was assigned.  
**Fix:**
```python
def _build_ui(self):
    self._tabs = []   # ← must exist BEFORE Sidebar is created
    self._sidebar = Sidebar(self, self._switch_tab)
    ...
```

**Dashboard window found via Win32:**
```python
import win32gui
# Result: HWND=2754008  'Antigravity Dashboard'  (234, 234, 1590, 1113)
```

---

### Step 4 — Open agy Interactive Terminal

**Python subprocess — new console window:**
```python
import subprocess
subprocess.Popen(
    ['cmd.exe', '/k', r'C:\Users\Mohammad Farhad\AppData\Local\agy\bin\agy.exe'],
    creationflags=subprocess.CREATE_NEW_CONSOLE,
)
```

**Terminal window found via Win32:**
```
HWND=460616
Title: 'C:\WINDOWS\SYSTEM32\cmd.exe - "C:\Users\Mohammad Farhad\AppData\Local\agy\bin\agy.exe"'
Rect: (18, 26, 1147, 661)
```

**agy startup screen showed:**
```
Accessing workspace: D:\AntigravityDashboard
Do you trust the contents of this project?
> Yes, I trust this folder
  No, exit
```

---

### Step 5 — Accept Trust Dialog

**Action:** pyautogui click on terminal center → press Enter

```python
import pyautogui, time
pyautogui.click(580, 340)   # click terminal to focus
time.sleep(0.3)
pyautogui.press('enter')    # confirm "Yes, I trust this folder"
time.sleep(3)
```

**Result — agy main screen:**
```
Antigravity CLI 1.0.8
farhadmohammad1996@gmail.com (Google AI Pro)
Gemini 3.5 Flash (High)          ← current model
D:/AntigravityDashboard
> _
? for shortcuts          Gemini 3.5 Flash (High)
```

---

### Step 6 — Change Model via `/model`

**Problem:** `pyautogui.typewrite()` loses keyboard focus when Python script exits — keypresses go to the wrong window.  
**Solution:** Use Win32 `AttachThreadInput` to force foreground, then send keys.

```python
import win32gui, win32process, ctypes, time, pyautogui

def force_focus(hwnd):
    cur = ctypes.windll.kernel32.GetCurrentThreadId()
    tgt = win32process.GetWindowThreadProcessId(hwnd)[0]
    ctypes.windll.user32.AttachThreadInput(cur, tgt, True)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    ctypes.windll.user32.AttachThreadInput(cur, tgt, False)
```

**Sequence:**
```python
# 1. Focus terminal + type /model
force_focus(460616)
pyautogui.click(100, 287)          # click prompt line
pyautogui.typewrite('/model', interval=0.08)
pyautogui.press('enter')

# Model menu appeared:
#   Gemini 3.5 Flash (Medium)
# > Gemini 3.5 Flash (High)   (current)
#   Gemini 3.5 Flash (Low)       ← target
#   Gemini 3.1 Pro (Low)
#   Claude Sonnet 4.6 (Thinking)
#   ...

# 2. Navigate DOWN once to select Low
force_focus(460616)
pyautogui.press('down')            # cursor moves to "Gemini 3.5 Flash (Low)"

# 3. Confirm selection
force_focus(460616)
pyautogui.press('enter')
```

**agy confirmed:**
```
> /model
  L  Model set to Gemini 3.5 Flash (High)    ← first attempt (missed)
> /model
  L  Model set to Gemini 3.5 Flash (Low)     ← success
                                    Gemini 3.5 Flash (Low)   ← status bar updated
```

---

### Step 7 — Send Prompt to Write File

**Prompt sent to agy (typed via pyautogui.typewrite):**
```
Write the 5 most important AI and tech picks for today June 16 2026 to the file 
D:\\AntigravityDashboard\\content\\top_picks.md — use emoji headlines, summaries, 
and why it matters sections. Overwrite the file.
```

**Known issue:** `pyautogui.typewrite()` does not handle `\t` (interprets as tab key).  
**Result:** Path was typed as `D:\AntigravityDashboard\contentop_picks.md` (missing `\t` before `op`).  
**agy created file at:** `D:\AntigravityDashboard\contentop_picks.md` (wrong location)

**agy internal actions visible in terminal:**
```
Thought for 2s, 271 tokens
Checking File Existence

WebSearch(AI tech news June 16 2026)    ← agy searched the web

Thought for 1s, 665 tokens
Organizing Tech Priorities

Create(D:/AntigravityDashboard/contentop_picks.md)   ← file written
```

**Fix — manually copy to correct path:**
```bash
cp "D:/AntigravityDashboard/contentop_picks.md" "D:/AntigravityDashboard/content/top_picks.md"
```

---

### Step 8 — Dashboard Auto-Renders

No button press needed. The `FileWatchTab._poll()` loop (running every 800ms inside the Tkinter `after()` scheduler) detected the new file at `content/top_picks.md` and called `set_text(textbox, content)`.

**Dashboard rendered:**
```markdown
# 🚀 Top 5 AI & Tech Picks: June 16, 2026

## 1. 🛑 U.S. Export Controls Force Anthropic's Frontier Models Offline
### Summary
Anthropic's Fable 5 and Mythos 5 taken offline due to U.S. export directive...
### Why It Matters
...

## 2. 🍂 AI Becomes the Frontline Defense for Global Biodiversity
...

## 3. 📉 Gartner Summit 2026: The Hard Shift from Hype to AI ROI
...

## 4. 💼 Ricoh Partners with Weaviate to Unlock Legacy Enterprise Data
...

## 5. 🔋 ELECTRA AI Showcases "AI Brain for Batteries" in London
...
```

---

## Issues Encountered & Fixes

| Issue | Cause | Fix |
|-------|-------|-----|
| `agy --print` returns empty stdout | agy uses Win32 `WriteConsole`, bypasses pipe | Switch to file-based integration |
| `AttributeError: _tabs` on startup | `Sidebar.select(0)` called before `self._tabs` assigned | Add `self._tabs = []` before Sidebar init |
| Keyboard focus lost between pyautogui calls | Each Python subprocess exits, focus returns to parent | `AttachThreadInput` + `SetForegroundWindow` in same script |
| `\t` in file path typed as Tab key | `pyautogui.typewrite()` interprets `\t` as Tab | Manual copy to correct path; future fix: use `pyautogui.write()` or clipboard paste |
| `/model` selected wrong option (High instead of Low) | Click coordinate was 1 row off | Used Down arrow key navigation instead of click |

---

## File Paths Reference

```
D:\AntigravityDashboard\
├── dashboard.py                  ← Main app (CustomTkinter, Python 3.11)
├── run.bat                       ← Double-click launcher
├── requirements.txt              ← customtkinter>=5.2.0, pillow>=10.0.0
└── content\                      ← agy writes here, dashboard reads here
    ├── top_picks.md              ← Tab: Top Picks Today
    ├── plan.md                   ← Tab: Today's Plan
    └── lessons.md                ← Tab: Today's 10 Lessons

C:\Users\Mohammad Farhad\
├── AppData\Local\agy\bin\agy.exe ← Antigravity CLI executable (in PATH as 'agy')
└── .gemini\antigravity-cli\
    ├── history.jsonl             ← All past prompts (Activities tab source)
    ├── conversations\*.db        ← SQLite, binary protobuf (not human-readable)
    └── settings.json             ← Model: "Gemini 3.5 Flash (High)" (default)
```

---

## Correct Prompts to Give agy (Copy-Paste Ready)

### Top Picks
```
Write the 5 most important AI and tech picks for today to the file D:\AntigravityDashboard\content\top_picks.md using emoji headlines, a Summary section, and a Why It Matters section for each. Overwrite the file completely.
```

### Today's Plan
```
Write a practical daily plan for a software engineer and AI developer to the file D:\AntigravityDashboard\content\plan.md using Morning / Afternoon / Evening sections with checkbox tasks (☐). Include a Top Priority section at the bottom. Overwrite the file.
```

### 10 Lessons
```
Write exactly 10 lessons for a software engineer working on AI to the file D:\AntigravityDashboard\content\lessons.md. Each lesson: number + emoji title, a What section (2-3 sentences), and an Action section (1 concrete thing to do today). Overwrite the file.
```

---

## Desktop Automation Tools Used

| Tool | Purpose |
|------|---------|
| `pyautogui` | Mouse click, keyboard input, screenshot |
| `win32gui` | Find window by title, get rect, enumerate windows |
| `win32process` | Get thread ID for `AttachThreadInput` |
| `win32con` | `SW_RESTORE` constant |
| `ctypes.windll.user32` | `AttachThreadInput`, `SetForegroundWindow`, `BringWindowToTop` |
| `PIL.Image` | Crop screenshots to window bounds for inspection |

---

## Key Lesson

> **agy (and likely most Gemini/Claude CLI tools on Windows) cannot be captured via stdout pipe.**  
> The correct integration pattern is: **prompt agy to write files → watch those files**.  
> agy has a built-in tool (`Create` / file write) that it uses when asked. The dashboard becomes a passive renderer, not an active requester.
