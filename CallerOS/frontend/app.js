const { useState, useEffect, useRef } = React;

// Simple Markdown / Codeblock Formatter helper
const renderMarkdown = (text) => {
  if (!text) return null;
  
  // Split content by code blocks ```...```
  const parts = text.split(/(```[\s\S]*?```)/g);
  return parts.map((part, idx) => {
    if (part.startsWith("```")) {
      const match = part.match(/```(\w*)\n([\s\S]*?)```/);
      const language = match ? match[1] : "";
      const code = match ? match[2] : part.slice(3, -3);
      
      return (
        <div key={idx} className="code-block-wrapper">
          <div className="code-header">
            <span>{language || "code"}</span>
            <button className="copy-btn" onClick={() => navigator.clipboard.writeText(code.strip ? code.strip() : code)}>
              Copy
            </button>
          </div>
          <pre><code>{code}</code></pre>
        </div>
      );
    }
    
    // Inline bold code formatting
    const lineParts = part.split(/\n/g);
    return (
      <p key={idx} style={{ marginBottom: "0.8em", lineHeight: "1.6" }}>
        {lineParts.map((line, lIdx) => (
          <span key={lIdx}>
            {lIdx > 0 && <br />}
            {line.split(/(\*\*.*?\*\*|`.*?`)/g).map((word, wIdx) => {
              if (word.startsWith("**") && word.endsWith("**")) {
                return <strong key={wIdx}>{word.slice(2, -2)}</strong>;
              }
              if (word.startsWith("`") && word.endsWith("`")) {
                return <code key={wIdx} className="inline-code">{word.slice(1, -1)}</code>;
              }
              return word;
            })}
          </span>
        ))}
      </p>
    );
  });
};

function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [status, setStatus] = useState({
    active_agent: "Director",
    workflow_status: "IDLE",
    current_model: "gpt-4o-mini",
    memory_status: "CONNECTED",
    tool_activity: "NONE"
  });

  // Settings states
  const [settings, setSettings] = useState({
    api_key: "",
    model: "gpt-4o-mini",
    log_level: "INFO"
  });

  // Poll status bar
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch("/api/status");
        if (res.ok) {
          const data = await res.json();
          setStatus(data);
        }
      } catch (err) {
        console.error("Failed to fetch status", err);
      }
    };
    
    fetchStatus();
    const interval = setInterval(fetchStatus, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="layout">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-dot"></div>
          <h2>GoblinOS</h2>
        </div>
        <nav className="nav-menu">
          <button 
            className={`nav-item ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            <i className="lucide-message-square nav-icon"></i>
            <span>Chat</span>
          </button>
          <button 
            className={`nav-item ${activeTab === "logs" ? "active" : ""}`}
            onClick={() => setActiveTab("logs")}
          >
            <i className="lucide-terminal nav-icon"></i>
            <span>Log Viewer</span>
          </button>
          <button 
            className={`nav-item ${activeTab === "settings" ? "active" : ""}`}
            onClick={() => setActiveTab("settings")}
          >
            <i className="lucide-settings nav-icon"></i>
            <span>Settings</span>
          </button>
        </nav>
      </aside>

      {/* Main Content Area */}
      <main className="main-panel">
        {activeTab === "chat" && <ChatScreen status={status} />}
        {activeTab === "logs" && <LogsScreen />}
        {activeTab === "settings" && <SettingsScreen settings={settings} setSettings={setSettings} />}
      </main>

      {/* Status Bar */}
      <footer className="status-bar">
        <div className="status-item">
          <span className="status-dot success"></span>
          <span>Agent: <strong>{status.active_agent}</strong></span>
        </div>
        <div className="status-item">
          <span>Workflow: <strong className={`workflow-${status.workflow_status.toLowerCase()}`}>{status.workflow_status}</strong></span>
        </div>
        <div className="status-item">
          <span>Model: <strong>{status.current_model}</strong></span>
        </div>
        <div className="status-item">
          <span>Memory: <strong className="success-text">{status.memory_status}</strong></span>
        </div>
        <div className="status-item">
          <span>Tool: <strong className={status.tool_activity !== "NONE" ? "warning-text" : ""}>{status.tool_activity}</strong></span>
        </div>
      </footer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Chat Screen Component
// ---------------------------------------------------------------------------
function ChatScreen({ status }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "System booted. GoblinOS is ready to receive requests." }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [backendError, setBackendError] = useState("");
  const messagesEndRef = useRef(null);

  // Auto scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages(prev => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);
    setBackendError("");

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userMsg })
      });
      
      if (!res.ok) {
        throw new Error("Backend connection error");
      }
      
      const data = await res.json();
      if (data.success) {
        setMessages(prev => [...prev, { role: "assistant", content: data.result }]);
      } else {
        setBackendError(data.error || "Execution failed.");
        setMessages(prev => [...prev, { role: "assistant", content: `❌ Error: ${data.error}` }]);
      }
    } catch (err) {
      setBackendError("Could not reach Python API server. Ensure run_ui.py is running.");
      setMessages(prev => [...prev, { role: "assistant", content: "❌ Connection error. Failed to execute request." }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="chat-container">
      <div className="chat-header">
        <h2>Orchestrator Workspace</h2>
        {status.workflow_status === "RUNNING" && (
          <div className="workflow-steps-progress">
            <span className="step active">Analyzing Query</span>
            <span className="step-arrow">→</span>
            <span className="step active">Executing Worker ({status.active_agent})</span>
            <span className="step-arrow">→</span>
            <span className="step">Writing Logs</span>
          </div>
        )}
      </div>

      <div className="messages-area">
        {messages.map((msg, index) => (
          <div key={index} className={`message-bubble ${msg.role}`}>
            <div className="message-header">
              <span>{msg.role === "user" ? "USER" : "GOBLIN_OS"}</span>
            </div>
            <div className="message-content">
              {msg.role === "assistant" ? renderMarkdown(msg.content) : <p>{msg.content}</p>}
            </div>
          </div>
        ))}
        {loading && (
          <div className="message-bubble assistant loading">
            <div className="message-header">Orchestrator Executing...</div>
            <div className="loading-spinner-wrapper">
              <div className="spinner"></div>
              <span>Active Agent: {status.active_agent} {status.tool_activity !== "NONE" && `(running ${status.tool_activity})`}</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {backendError && (
        <div className="error-panel">
          <i className="lucide-alert-circle"></i>
          <span>{backendError}</span>
        </div>
      )}

      <form onSubmit={handleSend} className="chat-input-area">
        <input
          type="text"
          placeholder="Ask GoblinOS to code, research or run tasks..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !input.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Logs Screen Component
// ---------------------------------------------------------------------------
function LogsScreen() {
  const [logs, setLogs] = useState([]);
  const [search, setSearch] = useState("");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/logs");
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error("Failed to fetch logs", err);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;
    const interval = setInterval(fetchLogs, 1000);
    return () => clearInterval(interval);
  }, [autoRefresh]);

  const filteredLogs = logs.filter(log => 
    log.message.toLowerCase().includes(search.toLowerCase()) || 
    log.level.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="logs-container">
      <div className="logs-header">
        <h2>System Logs</h2>
        <div className="logs-controls">
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button className="clear-btn" onClick={() => setSearch("")}>
              Clear
            </button>
          )}
          <label className="checkbox-wrapper">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
            <span>Auto Refresh</span>
          </label>
        </div>
      </div>

      <div className="logs-viewer">
        <table>
          <thead>
            <tr>
              <th style={{ width: "150px" }}>Timestamp</th>
              <th style={{ width: "80px" }}>Level</th>
              <th>Message</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log, idx) => (
              <tr key={idx}>
                <td className="log-timestamp">{log.timestamp}</td>
                <td>
                  <span className={`log-badge badge-${log.level.toLowerCase()}`}>
                    {log.level}
                  </span>
                </td>
                <td className="log-msg">{log.message}</td>
              </tr>
            ))}
            {filteredLogs.length === 0 && (
              <tr>
                <td colSpan="3" style={{ textAlign: "center", color: "var(--text-muted)", padding: "20px" }}>
                  No log records match filters.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Settings Screen Component
// ---------------------------------------------------------------------------
function SettingsScreen({ settings, setSettings }) {
  const [keyInput, setKeyInput] = useState("");
  const [modelInput, setModelInput] = useState("gpt-4o-mini");
  const [logLevelInput, setLogLevelInput] = useState("INFO");
  const [saveStatus, setSaveStatus] = useState("");

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await fetch("/api/settings");
        if (res.ok) {
          const data = await res.json();
          setSettings(data);
          setKeyInput(data.api_key);
          setModelInput(data.model);
          setLogLevelInput(data.log_level);
        }
      } catch (err) {
        console.error("Failed to load settings", err);
      }
    };
    loadSettings();
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    setSaveStatus("Saving...");
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          api_key: keyInput,
          model: modelInput,
          log_level: logLevelInput
        })
      });
      const data = await res.json();
      if (data.success) {
        setSaveStatus("Settings saved successfully!");
        setSettings({
          api_key: keyInput,
          model: modelInput,
          log_level: logLevelInput
        });
      } else {
        setSaveStatus(`Error saving settings: ${data.error}`);
      }
    } catch (err) {
      setSaveStatus("Failed to contact API server.");
    }
  };

  return (
    <div className="settings-container">
      <h2>System Configuration</h2>
      <p className="settings-sub">Configure API keys, logging outputs, and model parameters.</p>

      <form onSubmit={handleSave} className="settings-form">
        <div className="form-group">
          <label>OpenAI API Key (masked)</label>
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            placeholder="sk-..."
          />
        </div>

        <div className="form-group">
          <label>Model Selection</label>
          <select value={modelInput} onChange={(e) => setModelInput(e.target.value)}>
            <option value="gpt-4o-mini">gpt-4o-mini (Default)</option>
            <option value="gpt-4o">gpt-4o</option>
            <option value="o1-mini">o1-mini</option>
          </select>
        </div>

        <div className="form-group">
          <label>Logging Level</label>
          <select value={logLevelInput} onChange={(e) => setLogLevelInput(e.target.value)}>
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>

        <button type="submit" className="save-btn">
          Save Settings
        </button>

        {saveStatus && <p className="save-status">{saveStatus}</p>}
      </form>
    </div>
  );
}

// Render the application
const container = document.getElementById("root");
const root = ReactDOM.createRoot(container);
root.render(<App />);
