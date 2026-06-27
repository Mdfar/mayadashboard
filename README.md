# Maya Dashboard

A high-aesthetic, professional daily developer workspace and AI research dashboard. Built with CustomTkinter, it orchestrates workspace activities, daily plans, lessons learned, and a collaborative, human-in-the-loop AI Research & Writing workflow.

---

## 🚀 Key Features

*   **📰 Top Picks (Daily News)**: Curates and styles tech news articles, summaries, and impact highlights into a premium layout.
*   **✍️ Workspace Journals**: Integrates tabbed tracking pages for **Activities**, **Daily Plans** (with checkable items), and **Lessons Learned**.
*   **📊 Trends**: Automatically plots daily completion velocity and a 7-day completion calendar.
*   **💻 Workspace Terminal**: An embedded command prompt tab to run CLI commands and interact with AI tools directly.
*   **🔬 Collaborative AI Research & Writing (Step 1-5)**:
    1.  **Step 1: Discourse Research**: Fetches real-world practitioner opinions and feedback from Reddit, X/Twitter, dev.to, and Hacker News.
    2.  **Step 2: Content Outline**: Sets target section word counts and H2/H3 outline hierarchies.
    3.  **Step 3: Answer-First Drafting**: Writes full articles and structures 5 AI image prompts.
    4.  **Step 4: SEO Check & Factchecking**: Performs score breakdowns and audits named sources.
    5.  **Step 5: CMS / Git Publishing**: Publishes drafts directly to **WordPress** (REST API), **Ghost CMS** (Admin Token API), or local **GitHub repositories** (MDX structure).
*   **🖼️ Media Gallery & OG Banners**: Native offline branded 1200x630px cover generator (`og_cover.png`) using Pillow, AI prompt selection, and custom file uploads.
*   **🔍 Visual Diff Viewer**: Built-in side-by-side revision comparator showcasing color-coded differences between draft updates.
*   **📡 Version Update Checker**: Pings your website API on launch to display clickable version alerts (**`● Update Available`**) pointing to releases.

---

## 🔒 Security & Safety

To prevent accidental exposure of personal information or credentials:
1.  **Settings Template**: The local configuration file (`settings.json`) containing passwords, local system paths, and API keys is excluded from Git. Use the provided `settings.json.example` template as a reference.
2.  **Data Isolation**: All generated data files and databases (`content/`, `projects/`, `inbox/`, `.claude/`, `agentdb.rvf*`) are ignored by Git.

---

## 🛠️ Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Mdfar/mayadashboard.git
cd mayadashboard
```

### 2. Prepare Virtual Environment
You can run this project using standard Python tools or the faster **`uv`** package manager.

#### Option A: Using standard Python (venv)
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

#### Option B: Using `uv` (Recommended)
If you have `uv` installed, simply run the setup commands:
```bash
uv pip install -r requirements.txt
```

### 3. Setup Configuration
Copy the template file to create your active settings:
```bash
# Windows (CMD):
copy settings.json.example settings.json
# Windows (PowerShell) / macOS / Linux:
cp settings.json.example settings.json
```
Open `settings.json` and configure your local settings (e.g. `agy_path` path, WordPress, or Ghost CMS credentials).

### 4. Run the Dashboard
```bash
# Standard Python:
python dashboard.py

# Using uv:
uv run python dashboard.py
```
*(Windows users can also double-click `run.bat` to launch instantly).*

---

## 📖 Using the Collaborative Research Workspace

1.  Navigate to the **Research** tab in the sidebar.
2.  Enter your **Primary Topic** (e.g. `Enterprise Agentic AI`) and select a template.
3.  Add custom guidelines in the text box for **Step 1** and click **Run/Update Research**.
4.  Once the files are created, move sequentially through **Step 2 (Outline)**, **Step 3 (Draft)**, and **Step 4 (Verify)**.
5.  Use the **Visual Diff** tab to inspect changes between draft updates.
6.  Generate branded cover assets under **Images** and click **Sync & Publish** to push drafts to WordPress, Ghost CMS, or Git.

---

## 🔒 Safety & First-Run Security Instructions

Because the application compiles into standalone desktop binaries, your operating system will show a standard "unverified developer" warning the first time you run the compiled executable.

### 🛡️ Why is this harmless?
*   **100% Open Source**: Every line of code is fully visible in this repository. There are no tracking scripts, background analytics, or telemetries.
*   **No Installer Hooks**: The app runs directly in user space without modifying registry keys or core system directories.

### 💻 Windows: Bypassing SmartScreen
1. When opening `MayaDashboard.exe` for the first time, a blue **"Windows protected your PC"** window will appear.
2. Click **"More info"** under the text.
3. Click the **"Run anyway"** button.

### 🍏 macOS: Bypassing Gatekeeper
1. **Right-Click** (or hold **Control** and click) the `MayaDashboard` app icon and select **"Open"** from the menu.
2. In the popup that appears, click the **"Open"** button.
   *(Alternatively: Go to System Settings ➔ Privacy & Security, scroll down to Security, and click **"Open Anyway"**).*
