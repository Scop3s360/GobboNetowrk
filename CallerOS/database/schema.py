"""
Database Schema Definition
==========================
Defines the SQL queries for creating the initial tables in GoblinOS.
"""

# Initial database schema layout.
INITIAL_SCHEMA = [
    # Schema version tracking
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        migrated_at TEXT NOT NULL
    );
    """,
    # Conversations
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # Messages
    """
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
    );
    """,
    # Memories
    """
    CREATE TABLE IF NOT EXISTS memories (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        project TEXT,
        agent TEXT,
        content TEXT NOT NULL,
        tags TEXT NOT NULL,
        importance INTEGER NOT NULL,
        source TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """,
    # Workflow History
    """
    CREATE TABLE IF NOT EXISTS workflow_history (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        state TEXT NOT NULL,
        request TEXT NOT NULL,
        response TEXT NOT NULL,
        timestamp TEXT NOT NULL
    );
    """,
    # Application Settings
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """,
    # Logs
    """
    CREATE TABLE IF NOT EXISTS logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL,
        message TEXT NOT NULL
    );
    """
]
