# Maya Antigravity Dashboard

A high-aesthetic, professional workspace dashboard for software engineers and AI developers. Built with CustomTkinter, it orchestrates daily planning, lessons learned, completion analytics, and a collaborative, human-in-the-loop AI Research & Writing workflow.

---

## 🚀 Key Features

*   **📰 Top Picks (Daily News)**: Curates and styles tech news articles, summaries, and impact highlights into a premium magazine layout.
*   **✍️ Workspace Journals**: Integrates tabbed tracking pages for **Activities**, **Daily Plans** (with checkable items), and **Lessons Learned**.
*   **📊 Trends**: Automatically plots completion velocity and a 7-day completion calendar.
*   **💻 Workspace Terminal**: An embedded command prompt tab to run commands and interact with AI tools directly.
*   **⚙️ Settings**: Simple customization editor for themes, font properties, custom AI instruction headers, and publishing API credentials.
*   **🔬 Collaborative AI Research & Writing (Step 1-5)**:
    1.  **Step 1: Discourse Research**: Fetches real-world opinions and practitioner feedback from Reddit, X/Twitter, dev.to, and Hacker News.
    2.  **Step 2: Content Outline**: Sets target section word counts and H2/H3 outline hierarchies.
    3.  **Step 3: Answer-First Drafting**: Writes full articles and structures 5 AI image prompts.
    4.  **Step 4: SEO Check & Factchecking**: Performs score breakdowns and checks named sources.
    5.  **Step 5: CMS / Git Publishing**: Publishes drafts directly to **WordPress** (REST API), **Ghost CMS** (Admin Token API), or local **GitHub repositories** (MDX structure).
*   **🖼️ Media Gallery & OG Banners**: Native offline branded 1200x630px cover generator (`og_cover.png`) using Pillow, AI prompt selection, and custom file uploads.
*   **🔍 Visual Diff Viewer**: Built-in side-by-side revision comparator showcasing color-coded differences between draft updates.

---

## 🔒 Security Requisitions & Safety

To prevent accidental exposure of passwords, API keys, or directory structures:
1.  **Settings Template**: Do not commit `settings.json` directly. The repository includes `settings.json.example` which acts as an empty layout template.
2.  **Git Ignore Configuration**: The `.gitignore` is pre-configured to block local system configurations (`settings.json`), SQLite databases, lockfiles (`agentdb.rvf*`), and compiled content/research folders (`content/`, `agy_workspace/`).

---

## 🛠️ Installation & Setup

### 1. Clone & Prepare Virtual Environment
Clone the repository and initialize a virtual environment:

```bash
git clone https://github.com/yourusername/AntigravityDashboard.git
cd AntigravityDashboard

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
```

### 2. Install Dependencies
Install requirements for the GUI, markdown processing, Pillow images, and API communication:

```bash
pip install -r requirements.txt
```

### 3. Setup Configuration
Copy the template file to create your active settings file:

```bash
cp settings.json.example settings.json
```
Open `settings.json` and configure:
*   `agy_path`: The absolute path to your `agy` executable on disk.
*   Optional credentials for WordPress, Ghost CMS, or local Git repositories.

### 4. Run the Dashboard
Launch the interface:

```bash
python main.py
```

---

## 📖 Using the Collaborative Research Workspace

1.  Navigate to the **Research** tab.
2.  Enter your **Primary Topic** (e.g. `Enterprise Agentic AI`) and select a template type.
3.  Add custom instructions or update commentary to Step 1 and click **Run/Update Research**.
4.  Once the outline is generated in Step 2, run Step 3 to write the draft.
5.  Check revisions on the **Visual Diff** tab to see code changes.
6.  Generate images and click **Sync & Publish Article** under Step 5 to distribute drafts instantly.

---

## 🔒 Safety & First-Run Security Instructions

Because the application is compiled as an independent, open-source binary, Windows and macOS operating systems will show a standard "unverified developer" warning when running it for the first time.

### 🛡️ Why is this harmless?
*   **100% Open Source**: Every line of code is fully visible in this repository. There is no telemetry, background analytics, or hidden data transmission.
*   **No Installer Hooks**: The app runs directly in user space without modifying system files or registry keys.
*   **Standard Warning**: This popup appears for all indie applications that are not signed with developer certificates.

### 💻 Windows: Bypassing SmartScreen
1. When opening `MayaDashboard.exe` for the first time, a blue **"Windows protected your PC"** prompt will appear.
2. Click the small link labeled **"More info"** under the warning text.
3. Click the **"Run anyway"** button that appears. The app will launch and run normally from now on.

### 🍏 macOS: Bypassing Gatekeeper
1. Open your `Downloads` folder (or where you extracted the app zip).
2. **Right-Click** (or hold **Control** and click) the `MayaDashboard` app icon and select **"Open"** from the menu.
3. In the warning popup that appears, click the **"Open"** button.
   *(Alternatively: Go to System Settings ➔ Privacy & Security, scroll down to the Security section, and click **"Open Anyway"**).*
