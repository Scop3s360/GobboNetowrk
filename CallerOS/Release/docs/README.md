# GoblinOS / CallerOS (Version 1.0)

Welcome to **GoblinOS (CallerOS)**, a lightweight, modular agentic desktop operating system environment designed to orchestrate research and execution workflows through specialist AI workers.

---

## 1. Prerequisites

- **Python**: 3.10 or higher (Python 3.13 recommended)
- **Node.js** (Optional): Only required if you intend to run the electron wrapper client locally.
- **Web Browser**: Any modern web browser (Chrome, Edge, Firefox, Safari) if using the web UI directly.

---

## 2. Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Scop3s360/GobboNetowrk.git
   cd GobboNetowrk/CallerOS
   ```

2. **Set up a Virtual Environment**:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On Linux/macOS:
   source .venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables**:
   Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and fill in your OpenAI API credentials:
   ```env
   OPENAI_API_KEY=your-actual-api-key-here
   ```

---

## 3. Running the Application

### Option A: The Web Interface (Recommended)
1. Launch the built-in HTTP server:
   ```bash
   python run_ui.py
   ```
2. Open your browser and navigate to:
   ```text
   http://localhost:8080
   ```

### Option B: The Command Line Interface (CLI)
To run in terminal-only mode:
```bash
python main.py
```

### Option C: Standalone Windows Desktop App (V1.0.1 Release)
A complete, packaged version is generated under the `Release/` directory when running the build script:
1. Double-click `CallerOS.exe` inside the `Release/` directory.
2. The application will start its own local backend automatically in an invisible background process, and load the React workspace inside a native Edge WebView2 frame.
3. No terminal, Python, node, or web browser installation is required to distribute or run this bundle.

---

## 4. Build & Packaging Automation (Windows)

To clean, test, and build a standalone portable executable `Release/CallerOS.exe` automatically:
1. Run the build batch file:
   ```cmd
   build.bat
   ```
2. The script will automatically clean previous builds, verify requirements, execute all 315 tests, compile the executable, and assemble the portable `Release/` folder.

---

## 5. Running the Tests

To execute the complete unit and integration test suite (315 tests):
```bash
pytest
```

---

## 6. Troubleshooting

- **Missing `openai` module**: Ensure you activated the virtual environment and ran `pip install -r requirements.txt`.
- **Database Connection / Constraint Errors**: Delete the local SQLite file located at `logs/caller_os_memory.db` to allow the migration engine to rebuild the database schema automatically.
- **API Key not working**: Set your API key in the UI settings screen, or ensure the environment variable `OPENAI_API_KEY` is exported. Masked values (like `***` or `sk-123...cdef`) will be automatically ignored when updating settings to prevent overwriting active credentials.
- **WebView2 not loading**: On older Windows systems, WebView2 Runtime might not be installed. Modern Windows 10/11 comes with it pre-installed. If missing, it can be downloaded from Microsoft's site.

---

## 7. Project Workspace

GoblinOS/CallerOS features a complete Project Workspace system that isolates different codebases, design specifications, and topics.

- **Isolated Database & Files:** Each project has its own workspace directory (`workspaces/<project_id>/`) containing its own SQLite database (`workspace.db`), notes, and imported documents.
- **Document Importing & Auto-Chunking:** You can import `.md` and `.txt` documents into the active project. Markdown headers are parsed automatically to create context-aware section chunks in the project's memory.
- **Knowledge Index:** Uses SQLite's native `FTS5` virtual table indexing for rapid keyword and context relevance matching.
- **Context Injection:** When a project is active, the Director automatically queries the Context Engine to extract and rank relevant context snippets from the active workspace before worker execution, keeping specialists project-agnostic.

---

## 8. Integrated Development Workspace (IDE)

CallerOS includes a full, premium Integrated Development Workspace (IDE) featuring a side-by-side Monaco code editor, real-time Git status tracking, and a staged patch preview system.

- **Monaco Code Editor & Tabs:** Multi-tab file explorer that loads Monaco Editor directly from CDN. Standard keyboard shortcuts like `Ctrl+S` are hooked to write code directly back to the workspace.
- **Symbol Indexer:** An automatic indexing service (`project/index_service.py`) scans code structures using Python's native `ast` module and lexical regular expressions for C#. Extracted symbols (Classes, Methods, Imports) are saved in the isolated database and queried by the `ContextEngine` during normal chats.
- **Git Service:** Provides an isolated wrapper to verify repository presence, query branch/status updates, stage/unstage files, and perform commits.
- **Patch Approval System:** AI suggestions are generated as staged patches (`project/patch_system.py`) to prevent unauthorized modifications. The user can open a Monaco Diff Editor modal to inspect changes side-by-side before approving or rejecting.
- **Backups & Undo:** File operations (create, rename, delete, modify) are protected by a localized trash backup subsystem under `.trash/`, allowing instant rollbacks of the last operation.


