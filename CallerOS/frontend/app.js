const { useState, useEffect, useRef } = React;

// Simple Markdown / Codeblock Formatter helper
// Inline Markdown parser (links, inline code, bold text, and raw URLs)
const renderInlineMarkdown = (line) => {
  const tokens = line.split(/(\[.*?\]\(.*?\)|`.*?`|\*\*.*?\*\*)/g);
  return tokens.map((token, idx) => {
    if (token.startsWith("**") && token.endsWith("**")) {
      return <strong key={idx}>{token.slice(2, -2)}</strong>;
    }
    if (token.startsWith("`") && token.endsWith("`")) {
      return <code key={idx} className="inline-code">{token.slice(1, -1)}</code>;
    }
    if (token.startsWith("[") && token.includes("](")) {
      const match = token.match(/\[(.*?)\]\((.*?)\)/);
      if (match) {
        return (
          <a key={idx} href={match[2]} target="_blank" rel="noopener noreferrer" className="md-link">
            {match[1]}
          </a>
        );
      }
    }
    // Handle raw URLs
    const subTokens = token.split(/(\bhttps?:\/\/\S+\b)/g);
    return subTokens.map((subToken, sIdx) => {
      if (subToken.startsWith("http://") || subToken.startsWith("https://")) {
        return (
          <a key={`${idx}-${sIdx}`} href={subToken} target="_blank" rel="noopener noreferrer" className="md-link">
            {subToken}
          </a>
        );
      }
      return subToken;
    });
  });
};

// Block Markdown Formatter
const renderMarkdown = (text) => {
  if (!text) return null;
  if (typeof text !== "string") return String(text);

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
            <button className="copy-btn" onClick={() => navigator.clipboard.writeText(code.trim ? code.trim() : code)}>
              Copy Code
            </button>
          </div>
          <pre><code>{code}</code></pre>
        </div>
      );
    }
    
    // Process line-by-line
    const lines = part.split(/\n/g);
    return lines.map((line, lIdx) => {
      const trimmed = line.trim();
      
      // Headers
      if (trimmed.startsWith("# ")) {
        return <h1 key={lIdx} className="md-h1">{renderInlineMarkdown(trimmed.slice(2))}</h1>;
      }
      if (trimmed.startsWith("## ")) {
        return <h2 key={lIdx} className="md-h2">{renderInlineMarkdown(trimmed.slice(3))}</h2>;
      }
      if (trimmed.startsWith("### ")) {
        return <h3 key={lIdx} className="md-h3">{renderInlineMarkdown(trimmed.slice(4))}</h3>;
      }

      // Bullet lists
      if (trimmed.startsWith("- ") || trimmed.startsWith("* ") || trimmed.startsWith("• ")) {
        return (
          <ul key={lIdx} className="md-ul">
            <li className="md-li">{renderInlineMarkdown(trimmed.slice(2))}</li>
          </ul>
        );
      }

      // Spacer
      if (!trimmed) {
        return <div key={lIdx} className="md-spacer" />;
      }

      return (
        <p key={lIdx} className="md-p">
          {renderInlineMarkdown(line)}
        </p>
      );
    });
  });
};

// Rich UI Cards Presentation Layer
const renderMessageContent = (content) => {
  if (!content) return null;

  // 1. Research Card
  if (typeof content === "object" && content.type === "research") {
    const { summary, findings, sources, confidence } = content;
    
    let confLabel = "Unknown";
    let confClass = "conf-unknown";
    if (confidence >= 0.8) {
      confLabel = "High";
      confClass = "conf-high";
    } else if (confidence >= 0.4) {
      confLabel = "Medium";
      confClass = "conf-medium";
    } else if (confidence > 0) {
      confLabel = "Low";
      confClass = "conf-low";
    }

    return (
      <div className="research-card">
        <h1 className="card-title">Research Results</h1>
        
        <div className="card-section">
          <h2>Summary</h2>
          <div className="card-summary-text">{renderMarkdown(summary)}</div>
        </div>
        
        {findings && findings.length > 0 && (
          <div className="card-section">
            <h2>Key Findings</h2>
            <ul className="findings-list">
              {findings.map((finding, idx) => (
                <li key={idx}>{renderMarkdown(finding)}</li>
              ))}
            </ul>
          </div>
        )}
        
        {sources && sources.length > 0 && (
          <div className="card-section">
            <h2>Sources</h2>
            <ul className="sources-list">
              {sources.map((source, idx) => {
                const isUrl = source.startsWith("http://") || source.startsWith("https://");
                return (
                  <li key={idx}>
                    {isUrl ? (
                      <a href={source} target="_blank" rel="noopener noreferrer" className="source-link">
                        {source}
                      </a>
                    ) : (
                      <span>{source}</span>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        
        <div className="card-section confidence-section">
          <h2>Confidence</h2>
          <span className={`confidence-badge ${confClass}`}>{confLabel}</span>
        </div>
      </div>
    );
  }

  // 2. Developer / General Object Card
  if (typeof content === "object") {
    // Look for common fields. Supports fallback formats
    const explanation = content.explanation || content.result || content.summary || "";
    const code = content.code || "";
    const notes = content.notes || "";
    
    // If it's a general object without specific dev fields, format it as JSON code block
    if (!explanation && !code && !notes) {
      return (
        <div className="developer-card">
          <h1 className="card-title">{content.class_name || "Structured Response"}</h1>
          <div className="code-block-wrapper">
            <div className="code-header">
              <span>json</span>
              <button className="copy-btn" onClick={() => navigator.clipboard.writeText(JSON.stringify(content, null, 2))}>
                Copy JSON
              </button>
            </div>
            <pre><code>{JSON.stringify(content, null, 2)}</code></pre>
          </div>
        </div>
      );
    }

    return (
      <div className="developer-card">
        <h1 className="card-title">Developer Response</h1>
        
        {explanation && (
          <div className="card-section">
            <div className="card-explanation-text">{renderMarkdown(explanation)}</div>
          </div>
        )}
        
        {code && (
          <div className="card-section">
            <h2>Code</h2>
            <div className="code-block-wrapper">
              <div className="code-header">
                <span>code</span>
                <button className="copy-btn" onClick={() => navigator.clipboard.writeText(code)}>
                  Copy Code
                </button>
              </div>
              <pre><code>{code}</code></pre>
            </div>
          </div>
        )}
        
        {notes && (
          <div className="card-section">
            <h2>Notes</h2>
            <div className="card-notes-text">{renderMarkdown(notes)}</div>
          </div>
        )}
      </div>
    );
  }

  // 3. Fallback: string with Markdown support
  return renderMarkdown(content);
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

  // Update Lucide icons on tab change
  useEffect(() => {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }, [activeTab, status.active_project]);

  return (
    <div className="layout">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-dot"></div>
          <h2>{status.active_project && status.active_project !== "None" ? status.active_project : "GoblinOS"}</h2>
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
            className={`nav-item ${activeTab === "workspace" ? "active" : ""}`}
            onClick={() => setActiveTab("workspace")}
          >
            <i className="lucide-code nav-icon"></i>
            <span>Workspace</span>
          </button>
          <button 
            className={`nav-item ${activeTab === "projects" ? "active" : ""}`}
            onClick={() => setActiveTab("projects")}
          >
            <i className="lucide-folder nav-icon"></i>
            <span>Projects</span>
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
        {activeTab === "workspace" && <WorkspaceScreen status={status} />}
        {activeTab === "projects" && <ProjectsScreen />}
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
          <span>Project: <strong className="success-text">{status.active_project || "None"}</strong></span>
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
              {msg.role === "assistant" ? renderMessageContent(msg.content) : <p>{msg.content}</p>}
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

// ---------------------------------------------------------------------------
// Projects Screen Component
// ---------------------------------------------------------------------------
function ProjectsScreen() {
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [type, setType] = useState("Software");
  const [tags, setTags] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchProjects = async () => {
    try {
      const res = await fetch("/api/projects");
      if (res.ok) {
        const data = await res.json();
        setProjects(data);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchActiveAndDocs = async () => {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const data = await res.json();
        const activeName = data.active_project;
        
        // Find matching project from list
        const projRes = await fetch("/api/projects");
        if (projRes.ok) {
          const projs = await projRes.json();
          const activeProj = projs.find(p => p.name === activeName);
          setActiveProject(activeProj || null);
          
          if (activeProj) {
            const docsRes = await fetch("/api/projects/documents");
            if (docsRes.ok) {
              const docs = await docsRes.json();
              setDocuments(docs);
            }
          } else {
            setDocuments([]);
          }
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchProjects();
    fetchActiveAndDocs();
  }, []);

  useEffect(() => {
    if (window.lucide) {
      window.lucide.createIcons();
    }
  });

  const handleCreate = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;
    setLoading(true);
    setError("");

    try {
      const tagsList = tags.split(",").map(t => t.trim()).filter(Boolean);
      const res = await fetch("/api/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: name.trim(),
          description: description.trim(),
          type,
          tags: tagsList
        })
      });
      const data = await res.json();
      if (data.success) {
        setName("");
        setDescription("");
        setTags("");
        setShowModal(false);
        fetchProjects();
        // Switch to the newly created project
        await handleSwitch(data.project_id);
      } else {
        setError(data.error || "Failed to create project");
      }
    } catch (err) {
      setError("Connection error");
    } finally {
      setLoading(false);
    }
  };

  const handleSwitch = async (projectId) => {
    try {
      const res = await fetch("/api/projects/switch", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId })
      });
      const data = await res.json();
      if (data.success) {
        fetchProjects();
        fetchActiveAndDocs();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDelete = async (projectId, e) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this project? All isolated files, notes, and memories will be permanently destroyed.")) return;
    
    try {
      const res = await fetch("/api/projects/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId })
      });
      const data = await res.json();
      if (data.success) {
        fetchProjects();
        fetchActiveAndDocs();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    const reader = new FileReader();
    reader.onload = async (evt) => {
      const content = evt.target.result;
      try {
        const res = await fetch("/api/projects/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name: file.name,
            content
          })
        });
        const data = await res.json();
        if (data.success) {
          alert(`Imported ${file.name} successfully into ${data.document.chunks_count} chunks.`);
          fetchActiveAndDocs();
        } else {
          alert(`Error: ${data.error}`);
        }
      } catch (err) {
        alert("Connection error during document import.");
      }
    };
    reader.readAsText(file);
  };

  return (
    <div className="projects-container">
      <div className="projects-header">
        <div>
          <h1>Projects Workspace</h1>
          <p style={{ color: "var(--text-muted)", fontSize: "13px", marginTop: "4px" }}>
            Create isolated workspaces with independent files, memories, and index.
          </p>
        </div>
        <button className="btn-primary" onClick={() => setShowModal(true)}>
          <i data-lucide="plus"></i>
          <span>Create Project</span>
        </button>
      </div>

      <div className="projects-layout">
        {/* Projects Grid */}
        <div className="projects-grid">
          {projects.map((proj) => {
            const isActive = activeProject && activeProject.id === proj.id;
            return (
              <div 
                key={proj.id} 
                className={`project-card ${isActive ? "active" : ""}`}
                onClick={() => handleSwitch(proj.id)}
              >
                {isActive && <span className="project-active-badge">Active</span>}
                <div className="project-info">
                  <h2>{proj.name}</h2>
                  <p className="project-desc">{proj.description || "No description provided."}</p>
                  <span className="project-type-badge">{proj.type}</span>
                  {proj.tags && proj.tags.length > 0 && (
                    <div className="project-tags">
                      {proj.tags.map((t, idx) => (
                        <span key={idx} className="tag-badge">{t}</span>
                      ))}
                    </div>
                  )}
                </div>
                <div className="project-card-footer">
                  <span>Opened: {new Date(proj.last_opened_at).toLocaleDateString()}</span>
                  <button className="btn-danger" onClick={(e) => handleDelete(proj.id, e)}>
                    Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Selected Project Details Sidebar */}
        <div className="project-detail-panel">
          {activeProject ? (
            <>
              <h2 style={{ fontSize: "16px", fontWeight: 600 }}>{activeProject.name} Details</h2>
              <div style={{ display: "flex", flexDirection: "column", gap: "8px", fontSize: "13px" }}>
                <div><span style={{ color: "var(--text-muted)" }}>Type:</span> {activeProject.type}</div>
                <div><span style={{ color: "var(--text-muted)" }}>Created:</span> {new Date(activeProject.created_at).toLocaleDateString()}</div>
              </div>
              
              <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />
              
              <h3 style={{ fontSize: "14px", fontWeight: 600 }}>Import Documentation</h3>
              <p style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                Import Markdown (.md) or Text (.txt) files. Headings will automatically chunk sections to project memories.
              </p>
              
              <label className="import-dropzone">
                <i data-lucide="upload-cloud"></i>
                <span style={{ display: "block", fontSize: "13px", fontWeight: 500 }}>Select File to Import</span>
                <span style={{ display: "block", fontSize: "11px", marginTop: "4px" }}>Markdown or TXT</span>
                <input 
                  type="file" 
                  accept=".md,.txt" 
                  onChange={handleFileUpload} 
                  style={{ display: "none" }} 
                />
              </label>

              <hr style={{ border: "none", borderTop: "1px solid var(--border)" }} />

              <h3 style={{ fontSize: "14px", fontWeight: 600 }}>Imported Documents ({documents.length})</h3>
              <ul className="docs-list">
                {documents.map((doc) => (
                  <li key={doc.id} className="doc-item">
                    <div className="doc-item-info">
                      <span>{doc.name}</span>
                      <small>Imported: {new Date(doc.imported_at).toLocaleDateString()}</small>
                    </div>
                  </li>
                ))}
                {documents.length === 0 && (
                  <li style={{ color: "var(--text-muted)", fontSize: "12px", textAlign: "center", padding: "10px" }}>
                    No documents imported yet.
                  </li>
                )}
              </ul>
            </>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: "13px", textAlign: "center", padding: "20px" }}>
              Select or open a project to see details and import files.
            </div>
          )}
        </div>
      </div>

      {/* Create Project Modal */}
      {showModal && (
        <div className="modal-backdrop">
          <form onSubmit={handleCreate} className="modal-content">
            <h2 style={{ fontSize: "18px", fontWeight: 600 }}>Create New Project</h2>
            {error && <p style={{ color: "var(--danger)", fontSize: "13px" }}>{error}</p>}
            
            <div className="form-group">
              <label>Project Name *</label>
              <input 
                type="text" 
                required 
                value={name} 
                onChange={(e) => setName(e.target.value)} 
                placeholder="e.g. Unity Game System" 
              />
            </div>
            
            <div className="form-group">
              <label>Description</label>
              <textarea 
                value={description} 
                onChange={(e) => setDescription(e.target.value)} 
                placeholder="Short description of the workspace..." 
                rows="3"
              />
            </div>

            <div className="form-group">
              <label>Type</label>
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="Game">Game Development</option>
                <option value="Software">Software Engineering</option>
                <option value="Writing">Creative Writing</option>
                <option value="Research">Academic Research</option>
                <option value="Other">Other</option>
              </select>
            </div>

            <div className="form-group">
              <label>Tags (comma-separated)</label>
              <input 
                type="text" 
                value={tags} 
                onChange={(e) => setTags(e.target.value)} 
                placeholder="e.g. unity, dots, ecs" 
              />
            </div>

            <div className="modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setShowModal(false)} disabled={loading}>
                Cancel
              </button>
              <button type="submit" className="btn-primary" disabled={loading || !name.trim()}>
                {loading ? "Creating..." : "Create Project"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Workspace Screen (IDE) Component
// ---------------------------------------------------------------------------
function WorkspaceScreen({ status }) {
  const [sourceDir, setSourceDir] = useState("");
  const [sourceDirInput, setSourceDirInput] = useState("");
  const [files, setFiles] = useState([]);
  const [openTabs, setOpenTabs] = useState([]);
  const [activeTab, setActiveTab] = useState(null);
  const [dirtyTabs, setDirtyTabs] = useState(new Set());
  const [expandedFolders, setExpandedFolders] = useState(new Set());
  
  // Git State
  const [gitBranch, setGitBranch] = useState("None");
  const [gitStatus, setGitStatus] = useState({ staged: [], unstaged: [], untracked: [] });
  const [commitMessage, setCommitMessage] = useState("");
  
  // Patches State
  const [patches, setPatches] = useState([]);
  const [previewPatch, setPreviewPatch] = useState(null);
  
  // Logs State
  const [logs, setLogs] = useState([]);
  
  // Monaco States
  const containerRef = useRef(null);
  const diffContainerRef = useRef(null);
  const [editorInstance, setEditorInstance] = useState(null);
  const [diffEditorInstance, setDiffEditorInstance] = useState(null);
  const [cursorLine, setCursorLine] = useState(1);
  const [cursorColumn, setCursorColumn] = useState(1);
  const [selectedText, setSelectedText] = useState("");

  // Offline fallback editor states
  const [monacoStatus, setMonacoStatus] = useState("loading");
  const [fallbackContent, setFallbackContent] = useState("");

  // Load Monaco CDN
  useEffect(() => {
    let inst = null;
    
    // Set a timeout to switch to fallback if loading fails or takes too long (e.g. offline)
    const timeout = setTimeout(() => {
      setMonacoStatus(prev => prev === "loading" ? "failed" : prev);
    }, 2000);

    if (window.require) {
      window.require.config({ paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.39.0/min/vs' } });
      window.require(['vs/editor/editor'], function () {
        clearTimeout(timeout);
        setMonacoStatus("ready");
        if (!containerRef.current) return;
        inst = window.monaco.editor.create(containerRef.current, {
          theme: 'vs-dark',
          automaticLayout: true,
          minimap: { enabled: false },
          fontSize: 13,
          tabSize: 4,
          wordWrap: 'on'
        });
        setEditorInstance(inst);
      }, function(err) {
        console.error("Monaco load error, using fallback editor:", err);
        clearTimeout(timeout);
        setMonacoStatus("failed");
      });
    } else {
      clearTimeout(timeout);
      setMonacoStatus("failed");
    }
    
    return () => {
      clearTimeout(timeout);
      if (inst) {
        inst.dispose();
      }
    };
  }, []);

  const fetchStatusAndSource = async () => {
    try {
      const res = await fetch("/api/status");
      if (res.ok) {
        const data = await res.json();
        setSourceDir(data.source_dir || "");
        setSourceDirInput(data.source_dir || "");
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchFiles = async () => {
    try {
      const res = await fetch("/api/workspace/files");
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data)) {
          setFiles(data);
        }
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchGitStatus = async () => {
    try {
      const res = await fetch("/api/git/status");
      if (res.ok) {
        const data = await res.json();
        setGitBranch(data.branch || "None");
        setGitStatus(data.status || { staged: [], unstaged: [], untracked: [] });
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchPatches = async () => {
    try {
      const res = await fetch("/api/patches");
      if (res.ok) {
        const data = await res.json();
        setPatches(data.patches || []);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const fetchLogs = async () => {
    try {
      const res = await fetch("/api/logs");
      if (res.ok) {
        const data = await res.json();
        setLogs(data.logs || []);
      }
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    fetchStatusAndSource();
    fetchLogs();
    const logInterval = setInterval(fetchLogs, 3000);
    return () => clearInterval(logInterval);
  }, []);

  useEffect(() => {
    if (sourceDir) {
      fetchFiles();
      fetchGitStatus();
      fetchPatches();
    }
  }, [sourceDir]);

  // Handle Tab Switch / File loading in Monaco & Fallback Content
  useEffect(() => {
    if (!activeTab) return;
    
    fetch(`/api/workspace/file?path=${encodeURIComponent(activeTab)}`)
      .then(r => r.json())
      .then(data => {
        if (data.error) {
          alert(data.error);
          return;
        }
        
        setFallbackContent(data.content);
        
        if (monacoStatus === "ready" && editorInstance) {
          const ext = activeTab.split('.').pop().toLowerCase();
          let lang = 'plaintext';
          if (ext === 'py') lang = 'python';
          else if (ext === 'cs') lang = 'csharp';
          else if (ext === 'js') lang = 'javascript';
          else if (ext === 'ts') lang = 'typescript';
          else if (ext === 'json') lang = 'json';
          else if (ext === 'md') lang = 'markdown';
          else if (ext === 'yaml' || ext === 'yml') lang = 'yaml';
          
          const uri = window.monaco.Uri.file(activeTab);
          let model = window.monaco.editor.getModel(uri);
          if (!model) {
            model = window.monaco.editor.createModel(data.content, lang, uri);
          } else {
            if (!dirtyTabs.has(activeTab)) {
              model.setValue(data.content);
            }
          }
          
          editorInstance.setModel(model);
          
          editorInstance.onDidChangeCursorPosition(e => {
            setCursorLine(e.position.lineNumber);
            setCursorColumn(e.position.column);
          });
          
          editorInstance.onDidChangeCursorSelection(e => {
            const selText = editorInstance.getModel().getValueInRange(e.selection);
            setSelectedText(selText);
          });
          
          model.onDidChangeContent(() => {
            setDirtyTabs(prev => {
              const next = new Set(prev);
              next.add(activeTab);
              return next;
            });
          });
        }
      });
  }, [activeTab, editorInstance, monacoStatus]);

  // Ctrl+S Command registration
  useEffect(() => {
    if (!editorInstance) return;
    editorInstance.addCommand(window.monaco.KeyMod.CtrlCmd | window.monaco.KeyCode.KeyS, () => {
      handleSaveActiveTab();
    });
  }, [editorInstance, activeTab]);

  const handleSaveActiveTab = async () => {
    if (!editorInstance || !activeTab) return;
    const content = editorInstance.getValue();
    try {
      const res = await fetch('/api/workspace/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab, content })
      });
      const data = await res.json();
      if (data.success) {
        setDirtyTabs(prev => {
          const next = new Set(prev);
          next.delete(activeTab);
          return next;
        });
        fetchGitStatus();
      } else {
        alert("Failed to save: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };
  const handleSaveFallback = async () => {
    if (!activeTab) return;
    try {
      const res = await fetch('/api/workspace/file', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: activeTab, content: fallbackContent })
      });
      const data = await res.json();
      if (data.success) {
        setDirtyTabs(prev => {
          const next = new Set(prev);
          next.delete(activeTab);
          return next;
        });
        fetchGitStatus();
      } else {
        alert("Failed to save: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSetSource = async (e) => {
    e.preventDefault();
    if (!sourceDirInput.trim()) return;
    try {
      const res = await fetch("/api/workspace/set_source", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_dir: sourceDirInput.trim() })
      });
      const data = await res.json();
      if (data.success) {
        setSourceDir(sourceDirInput.trim());
      } else {
        alert("Error: " + data.error);
      }
    } catch (err) {
      alert("Failed to set source folder.");
    }
  };

  const handleCreateFile = async () => {
    const name = prompt("Enter relative file path to create (e.g. src/utils.py):");
    if (!name) return;
    try {
      const res = await fetch("/api/workspace/file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: name, content: "", isDir: false })
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
        fetchGitStatus();
        handleOpenFile(name);
      } else {
        alert("Error: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleCreateFolder = async () => {
    const name = prompt("Enter relative folder path to create (e.g. assets):");
    if (!name) return;
    try {
      const res = await fetch("/api/workspace/file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: name, content: "", isDir: true })
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
      } else {
        alert("Error: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleRenameFile = async (path) => {
    const newName = prompt(`Rename / Move '${path}' to:`, path);
    if (!newName || newName === path) return;
    try {
      const res = await fetch("/api/workspace/file/rename", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_path: path, new_path: newName })
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
        fetchGitStatus();
        
        if (openTabs.includes(path)) {
          setOpenTabs(prev => prev.map(t => t === path ? newName : t));
          if (activeTab === path) {
            setActiveTab(newName);
          }
        }
      } else {
        alert("Error: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteFile = async (path) => {
    if (!confirm(`Are you sure you want to delete '${path}'? This action can be undone.`)) return;
    try {
      const res = await fetch("/api/workspace/file/delete", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path })
      });
      const data = await res.json();
      if (data.success) {
        fetchFiles();
        fetchGitStatus();
        handleCloseTab(path);
      } else {
        alert("Error: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleUndo = async () => {
    try {
      const res = await fetch("/api/workspace/file/undo", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        alert("Last operation undone successfully.");
        fetchFiles();
        fetchGitStatus();
      } else {
        alert("Nothing to undo: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleTriggerIndex = async () => {
    try {
      const res = await fetch("/api/workspace/index", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        alert(`Scanned source tree. Indexed ${data.indexed.total_symbols} symbols across ${data.indexed.total_files} files.`);
      } else {
        alert("Indexing failed: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Git operations
  const handleStageFile = async (path) => {
    try {
      const res = await fetch("/api/git/stage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path })
      });
      if (res.ok) fetchGitStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleUnstageFile = async (path) => {
    try {
      const res = await fetch("/api/git/unstage", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path })
      });
      if (res.ok) fetchGitStatus();
    } catch (err) {
      console.error(err);
    }
  };

  const handleCommit = async (e) => {
    e.preventDefault();
    if (!commitMessage.trim()) return;
    try {
      const res = await fetch("/api/git/commit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: commitMessage })
      });
      const data = await res.json();
      if (data.success) {
        alert("Changes committed successfully:\n" + data.output);
        setCommitMessage("");
        fetchGitStatus();
      } else {
        alert("Commit failed: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Patches operations
  const handlePreviewPatch = (patch) => {
    setPreviewPatch(patch);
  };

  useEffect(() => {
    if (!previewPatch || !window.monaco) return;
    
    const timer = setTimeout(() => {
      if (!diffContainerRef.current) return;
      
      const diffEditor = window.monaco.editor.createDiffEditor(diffContainerRef.current, {
        theme: 'vs-dark',
        readOnly: true,
        automaticLayout: true
      });
      setDiffEditorInstance(diffEditor);
      
      const ext = previewPatch.target_file.split('.').pop().toLowerCase();
      let lang = 'plaintext';
      if (ext === 'py') lang = 'python';
      else if (ext === 'cs') lang = 'csharp';
      else if (ext === 'js') lang = 'javascript';
      
      diffEditor.setModel({
        original: window.monaco.editor.createModel(previewPatch.original_content, lang),
        modified: window.monaco.editor.createModel(previewPatch.patched_content, lang)
      });
    }, 100);
    
    return () => {
      clearTimeout(timer);
      if (diffEditorInstance) {
        diffEditorInstance.dispose();
      }
    };
  }, [previewPatch]);

  const handleApprovePatch = async (path) => {
    try {
      const res = await fetch("/api/patches/apply", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_file: path })
      });
      const data = await res.json();
      if (data.success) {
        setPreviewPatch(null);
        fetchPatches();
        fetchGitStatus();
        fetchFiles();
        
        if (openTabs.includes(path)) {
          if (activeTab === path) {
            setActiveTab(null);
            setTimeout(() => setActiveTab(path), 50);
          }
        }
      } else {
        alert("Apply patch failed: " + data.error);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleRejectPatch = async (path) => {
    try {
      const res = await fetch("/api/patches/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target_file: path })
      });
      if (res.ok) {
        setPreviewPatch(null);
        fetchPatches();
      }
    } catch (err) {
      console.error(err);
    }
  };

  // Tab controls
  const handleOpenFile = (path) => {
    if (!openTabs.includes(path)) {
      setOpenTabs(prev => [...prev, path]);
    }
    setActiveTab(path);
  };

  const handleCloseTab = (path) => {
    setOpenTabs(prev => prev.filter(t => t !== path));
    if (activeTab === path) {
      const remaining = openTabs.filter(t => t !== path);
      setActiveTab(remaining.length > 0 ? remaining[remaining.length - 1] : null);
    }
    setDirtyTabs(prev => {
      const next = new Set(prev);
      next.delete(path);
      return next;
    });
  };

  const toggleFolder = (path) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };

  const renderExplorerTree = () => {
    const tree = { name: "root", isDir: true, path: "", children: {} };
    
    files.forEach(item => {
      const parts = item.path.split("/");
      let current = tree;
      
      parts.forEach((part, idx) => {
        const isLast = idx === parts.length - 1;
        const curPath = parts.slice(0, idx + 1).join("/");
        
        if (!current.children[part]) {
          current.children[part] = {
            name: part,
            path: curPath,
            isDir: !isLast || item.isDir,
            children: {}
          };
        }
        current = current.children[part];
      });
    });

    const renderNode = (node, depth = 0) => {
      if (node.name === "root" && Object.keys(node.children).length === 0) {
        return (
          <div style={{ color: "var(--text-muted)", fontSize: "12px", padding: "10px" }}>
            Source directory is empty.
          </div>
        );
      }
      
      const isExpanded = expandedFolders.has(node.path);
      const childKeys = Object.keys(node.children).sort((a,b) => {
        const aNode = node.children[a];
        const bNode = node.children[b];
        if (aNode.isDir && !bNode.isDir) return -1;
        if (!aNode.isDir && bNode.isDir) return 1;
        return a.localeCompare(b);
      });

      return (
        <div key={node.path} style={{ paddingLeft: `${depth * 8}px` }}>
          {node.name !== "root" && (
            <div 
              className={`explorer-item ${node.isDir ? "directory" : ""} ${activeTab === node.path ? "active" : ""}`}
              onClick={() => node.isDir ? toggleFolder(node.path) : handleOpenFile(node.path)}
              style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <i className={`lucide-${node.isDir ? (isExpanded ? "folder-open" : "folder") : "file-code"}`} style={{ width: 14, height: 14 }}></i>
                <span>{node.name}</span>
              </div>
              
              <div className="explorer-item-actions" style={{ display: 'flex', gap: '4px' }} onClick={e => e.stopPropagation()}>
                <button className="git-btn-action" onClick={() => handleRenameFile(node.path)} title="Rename/Move">
                  <i className="lucide-edit" style={{ width: 10, height: 10 }}></i>
                </button>
                <button className="git-btn-action" onClick={() => handleDeleteFile(node.path)} title="Delete">
                  <i className="lucide-trash" style={{ width: 10, height: 10 }}></i>
                </button>
              </div>
            </div>
          )}
          {node.isDir && (node.name === "root" || isExpanded) && (
            <div>
              {childKeys.map(k => renderNode(node.children[k], node.name === "root" ? 0 : depth + 1))}
            </div>
          )}
        </div>
      );
    };

    return renderNode(tree);
  };

  return (
    <div className="workspace-container">
      {/* Left Sidebar */}
      <aside className="workspace-sidebar">
        <div style={{ padding: "12px", borderBottom: "1px solid var(--border)" }}>
          <form onSubmit={handleSetSource} style={{ display: "flex", gap: "6px" }}>
            <input 
              type="text" 
              value={sourceDirInput}
              onChange={e => setSourceDirInput(e.target.value)}
              placeholder="Source Path (e.g. C:/src)"
              className="git-commit-input"
              style={{ flex: 1, padding: "4px 8px", fontSize: "12px" }}
            />
            <button type="submit" className="btn-primary" style={{ padding: "4px 8px", fontSize: "11px" }}>
              Bind
            </button>
          </form>
        </div>

        <div className="sidebar-section-header">
          <span>Explorer</span>
          <div style={{ display: "flex", gap: "6px" }}>
            <button className="git-btn-action" onClick={handleCreateFile} title="Create File">
              <i className="lucide-file-plus" style={{ width: 13, height: 13 }}></i>
            </button>
            <button className="git-btn-action" onClick={handleCreateFolder} title="Create Folder">
              <i className="lucide-folder-plus" style={{ width: 13, height: 13 }}></i>
            </button>
            <button className="git-btn-action" onClick={handleUndo} title="Undo Last File Action">
              <i className="lucide-undo-2" style={{ width: 13, height: 13 }}></i>
            </button>
            <button className="git-btn-action" onClick={handleTriggerIndex} title="Re-scan Symbol Index">
              <i className="lucide-search-code" style={{ width: 13, height: 13 }}></i>
            </button>
          </div>
        </div>

        {sourceDir ? (
          <div className="explorer-tree">
            {renderExplorerTree()}
          </div>
        ) : (
          <div style={{ color: "var(--text-muted)", fontSize: "12px", padding: "16px", textAlign: "center" }}>
            Set a source directory at the top to browse files.
          </div>
        )}

        {/* Git panel */}
        <div className="git-changes-panel">
          <div className="sidebar-section-header">
            <span>Git Panel ({gitBranch})</span>
            <button className="git-btn-action" onClick={fetchGitStatus} title="Refresh Git">
              <i className="lucide-refresh-cw" style={{ width: 12, height: 12 }}></i>
            </button>
          </div>
          
          <div className="git-list">
            {gitStatus.staged.map(f => (
              <div key={f} className="git-item">
                <span style={{ color: "var(--accent)", fontWeight: 500 }}>Staged: {f}</span>
                <button className="git-btn-action" onClick={() => handleUnstageFile(f)} title="Unstage">
                  <i className="lucide-minus-circle" style={{ width: 12, height: 12 }}></i>
                </button>
              </div>
            ))}
            
            {gitStatus.unstaged.map(f => (
              <div key={f} className="git-item">
                <span style={{ color: "var(--warning)" }}>Unstaged: {f}</span>
                <button className="git-btn-action" onClick={() => handleStageFile(f)} title="Stage">
                  <i className="lucide-plus-circle" style={{ width: 12, height: 12 }}></i>
                </button>
              </div>
            ))}
            
            {gitStatus.untracked.map(f => (
              <div key={f} className="git-item">
                <span style={{ color: "var(--text-muted)" }}>Untracked: {f}</span>
                <button className="git-btn-action" onClick={() => handleStageFile(f)} title="Stage">
                  <i className="lucide-plus-circle" style={{ width: 12, height: 12 }}></i>
                </button>
              </div>
            ))}

            {gitStatus.staged.length === 0 && gitStatus.unstaged.length === 0 && gitStatus.untracked.length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: "11px", textAlign: "center", padding: "10px" }}>
                No changes detected.
              </div>
            )}
          </div>

          <form onSubmit={handleCommit} className="git-commit-form">
            <input 
              type="text" 
              value={commitMessage}
              onChange={e => setCommitMessage(e.target.value)}
              placeholder="Commit message..."
              className="git-commit-input"
              required
            />
            <button type="submit" className="btn-primary" style={{ padding: "6px", fontSize: "12px", width: "100%", justifyContent: "center" }}>
              Commit Changes
            </button>
          </form>
        </div>
      </aside>

      {/* Center Panel */}
      <section className="workspace-editor-pane">
        <div className="editor-tabs-bar">
          {openTabs.map(tab => {
            const isActive = activeTab === tab;
            const isDirty = dirtyTabs.has(tab);
            return (
              <div 
                key={tab} 
                className={`editor-tab ${isActive ? "active" : ""}`}
                onClick={() => handleOpenFile(tab)}
              >
                <span>{tab.split('/').pop()}</span>
                {isDirty && <span className="editor-tab-dirty"></span>}
                <span className="editor-tab-close" onClick={e => { e.stopPropagation(); handleCloseTab(tab); }}>
                  ×
                </span>
              </div>
            );
          })}
        </div>

        <div className="editor-container">
          {monacoStatus === "ready" ? (
            <div ref={containerRef} className="monaco-editor-instance"></div>
          ) : activeTab ? (
            <div style={{ width: "100%", height: "100%", display: "flex", flexDirection: "column" }}>
              <div style={{
                padding: "6px 16px",
                backgroundColor: "#1a0e0e",
                color: "#ffc107",
                fontSize: "11px",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                borderBottom: "1px solid var(--border)"
              }}>
                <span>Offline Fallback Editor (Monaco CDN unreachable)</span>
                <button onClick={handleSaveFallback} className="btn-primary" style={{ padding: "2px 8px", fontSize: "11px" }}>
                  Save (Ctrl+S)
                </button>
              </div>
              <textarea
                className="fallback-textarea"
                value={fallbackContent}
                onChange={e => {
                  setFallbackContent(e.target.value);
                  setDirtyTabs(prev => {
                    const next = new Set(prev);
                    next.add(activeTab);
                    return next;
                  });
                }}
                style={{
                  flex: 1,
                  backgroundColor: "#0B0E14",
                  color: "#A9B2C3",
                  border: "none",
                  padding: "16px",
                  fontFamily: "Consolas, Courier New, monospace",
                  fontSize: "13px",
                  lineHeight: "1.6",
                  resize: "none",
                  outline: "none"
                }}
                onKeyDown={e => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 's') {
                    e.preventDefault();
                    handleSaveFallback();
                  }
                }}
              />
            </div>
          ) : null}
          
          {!activeTab && (
            <div style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              height: "100%",
              color: "var(--text-muted)",
              fontSize: "14px",
              gap: "8px"
            }}>
              <i className="lucide-code-2" style={{ width: 36, height: 36, color: "var(--accent)" }}></i>
              <span>Select a file from the explorer to open it in the editor.</span>
            </div>
          )}
        </div>

        {activeTab && (
          <div style={{
            height: "22px",
            backgroundColor: "var(--bg-panel)",
            borderTop: "1px solid var(--border)",
            display: "flex",
            justifyContent: "flex-end",
            alignItems: "center",
            padding: "0 16px",
            fontSize: "11px",
            color: "var(--text-muted)",
            gap: "12px"
          }}>
            <span>Tab size: 4</span>
            <span>UTF-8</span>
            <span>Ln {cursorLine}, Col {cursorColumn}</span>
          </div>
        )}
      </section>

      {/* Right Sidebar */}
      <aside className="workspace-ai-pane">
        <ChatScreen status={status} hideHeader={true} />
        
        <div className="patches-panel">
          <div className="sidebar-section-header">
            <span>Staged Patches ({patches.length})</span>
          </div>
          
          <div className="patches-list">
            {patches.map(patch => (
              <div key={patch.target_file} className="patch-card">
                <div className="patch-card-header">
                  <span className="patch-file-name">{patch.target_file.split('/').pop()}</span>
                  <span style={{ color: "var(--accent)", fontSize: "10px", fontWeight: 600 }}>PENDING</span>
                </div>
                <p className="patch-reason">{patch.reason || "AI modification proposed."}</p>
                <div className="patch-actions">
                  <button className="btn-secondary" style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => handlePreviewPatch(patch)}>
                    Diff View
                  </button>
                  <button className="btn-danger" style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => handleRejectPatch(patch.target_file)}>
                    Reject
                  </button>
                  <button className="btn-primary" style={{ padding: "4px 8px", fontSize: "11px" }} onClick={() => handleApprovePatch(patch.target_file)}>
                    Approve
                  </button>
                </div>
              </div>
            ))}
            
            {patches.length === 0 && (
              <div style={{ color: "var(--text-muted)", fontSize: "12px", textAlign: "center", padding: "20px" }}>
                No pending patches generated.
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Bottom Panel */}
      <footer className="workspace-console-pane">
        <div className="console-header">
          <span>Developer Console Logs</span>
          <button className="git-btn-action" onClick={() => setLogs([])} title="Clear Logs">
            <i className="lucide-trash" style={{ width: 12, height: 12 }}></i>
          </button>
        </div>
        <div className="console-logs">
          {logs.map((logItem, idx) => {
            const levelClass = logItem.level.toLowerCase();
            return (
              <div key={idx} className={`console-log-line ${levelClass}`}>
                [{logItem.timestamp}] {logItem.level}: {logItem.message}
              </div>
            );
          })}
        </div>
      </footer>

      {/* Monaco Diff Overlay */}
      {previewPatch && (
        <div className="diff-modal-overlay">
          <div className="diff-modal-container">
            <div className="diff-modal-header">
              <span className="diff-modal-title">Staged Change Preview: {previewPatch.target_file}</span>
              <div style={{ display: "flex", gap: "10px" }}>
                <button className="btn-secondary" onClick={() => setPreviewPatch(null)}>
                  Close
                </button>
                <button className="btn-danger" onClick={() => handleRejectPatch(previewPatch.target_file)}>
                  Reject Patch
                </button>
                <button className="btn-primary" onClick={() => handleApprovePatch(previewPatch.target_file)}>
                  Approve and Apply
                </button>
              </div>
            </div>
            <div className="diff-editor-wrapper">
              {monacoStatus === "ready" ? (
                <div ref={diffContainerRef} style={{ width: "100%", height: "100%", position: "absolute" }}></div>
              ) : (
                <div style={{ display: "flex", width: "100%", height: "100%", backgroundColor: "#080A0F" }}>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column", borderRight: "1px solid var(--border)" }}>
                    <div style={{ padding: "8px 16px", backgroundColor: "#3a1d1d", fontSize: "12px", color: "#ffa3a3", fontWeight: 600 }}>Original File</div>
                    <textarea 
                      readOnly 
                      value={previewPatch.original_content}
                      style={{ flex: 1, backgroundColor: "#140e0e", color: "#e88b8b", border: "none", padding: "12px", fontFamily: "monospace", resize: "none", outline: "none" }}
                    />
                  </div>
                  <div style={{ flex: 1, display: "flex", flexDirection: "column" }}>
                    <div style={{ padding: "8px 16px", backgroundColor: "#1e3a1d", fontSize: "12px", color: "#a3ffa3", fontWeight: 600 }}>Proposed Changes</div>
                    <textarea 
                      readOnly 
                      value={previewPatch.patched_content}
                      style={{ flex: 1, backgroundColor: "#0f140e", color: "#8be88b", border: "none", padding: "12px", fontFamily: "monospace", resize: "none", outline: "none" }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Render the application
const container = document.getElementById("root");
const root = ReactDOM.createRoot(container);
root.render(<App />);
