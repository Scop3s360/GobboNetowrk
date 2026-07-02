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

### Option C: The Electron Desktop Wrapper (Optional)
If you have Node.js installed:
```bash
cd frontend
npm install
npm start
```

---

## 4. Running the Tests

To execute the complete unit and integration test suite (315 tests):
```bash
pytest
```

---

## 5. Troubleshooting

- **Missing `openai` module**: Ensure you activated the virtual environment and ran `pip install -r requirements.txt`.
- **Database Connection / Constraint Errors**: Delete the local SQLite file located at `logs/caller_os_memory.db` to allow the migration engine to rebuild the database schema automatically.
- **API Key not working**: Set your API key in the UI settings screen, or ensure the environment variable `OPENAI_API_KEY` is exported. Masked values (like `***` or `sk-123...cdef`) will be automatically ignored when updating settings to prevent overwriting active credentials.
