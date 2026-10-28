"""
Desktop Application Launcher for YouTube Study Notes.
Opens the tool as a standalone Windows Desktop App (no browser tabs or address bar).
"""

import os
import sys
import time
import socket
import subprocess
from pathlib import Path

PORT = 8501
URL = f"http://localhost:{PORT}"
PROJECT_DIR = Path(__file__).parent.resolve()
VENV_PYTHON = PROJECT_DIR / ".venv" / "Scripts" / "python.exe"
STREAMLIT_EXE = PROJECT_DIR / ".venv" / "Scripts" / "streamlit.exe"


def is_port_in_use(port: int) -> bool:
    """Check if the Streamlit server is already running."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) == 0


def find_browser_app_executable() -> str:
    """Locate Chrome or Edge to run in standalone app mode."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return ""


def main():
    print("[*] Initializing YouTube Study Studio Desktop App...")

    # 1. Start Streamlit server in the background if not already active
    if not is_port_in_use(PORT):
        print("[*] Starting backend engine...")
        cmd = [
            str(STREAMLIT_EXE),
            "run",
            str(PROJECT_DIR / "app.py"),
            "--server.port", str(PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false"
        ]
        # Start detached background process on Windows
        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_DIR),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )

        # Wait until server is up
        print("[*] Waiting for server to connect...")
        for _ in range(15):
            time.sleep(0.5)
            if is_port_in_use(PORT):
                break

    # 2. Launch in standalone desktop window (app mode: no tabs, no address bar)
    browser_exe = find_browser_app_executable()
    if browser_exe:
        print(f"[*] Launching standalone app window via {Path(browser_exe).name}...")
        subprocess.Popen([
            browser_exe,
            f"--app={URL}",
            "--window-size=1360,860",
            "--window-position=100,50"
        ])
    else:
        # Fallback to standard default browser if neither Chrome nor Edge found
        import webbrowser
        webbrowser.open(URL)

    print("[OK] App window launched successfully!")


if __name__ == "__main__":
    main()
