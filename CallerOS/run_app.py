"""
CallerOS Native Desktop Window Entry Point
==========================================
Wraps the built-in HTTP server and launches a native webview window using Webview2.
Hides any console/terminal window when packaged.
"""

from __future__ import annotations

import sys
import os
import time
import threading
import logging
import ctypes
from pathlib import Path
from http.server import HTTPServer

# Adjust path to find core packages
sys.path.insert(0, str(Path(__file__).parent))

import webview
from run_ui import run_server, app, db_mgr

log = logging.getLogger(__name__)

def main() -> None:
    try:
        # Port configuration
        port = 8080
        
        # Start server in a background daemon thread
        server_thread = threading.Thread(target=run_server, args=(port,), daemon=True)
        server_thread.start()
        
        # Give the server a small moment to bind to the port
        time.sleep(0.5)
        
        # Locate the application icon
        icon_path = Path(__file__).parent / "app_icon.ico"
        icon_str = str(icon_path.resolve()) if icon_path.is_file() else None
        
        # Create a native desktop window
        # WebView2 on Windows is used by default.
        window = webview.create_window(
            title="CallerOS",
            url=f"http://127.0.0.1:{port}",
            width=1200,
            height=800,
            resizable=True,
            min_size=(800, 600)
        )
        
        # Run pywebview main window loop (blocks until window is closed)
        webview.start()
        
    except Exception as exc:
        # Friendly native Windows error dialog instead of silent crash or traceback
        error_msg = f"Failed to start CallerOS:\n\n{str(exc)}\n\nPlease ensure your environment variables are configured correctly."
        ctypes.windll.user32.MessageBoxW(0, error_msg, "CallerOS - Startup Error", 0x10)
        sys.exit(1)
    finally:
        # Graceful database and core application cleanup
        try:
            db_mgr.close()
            app.shutdown()
        except Exception:
            pass

if __name__ == "__main__":
    main()
