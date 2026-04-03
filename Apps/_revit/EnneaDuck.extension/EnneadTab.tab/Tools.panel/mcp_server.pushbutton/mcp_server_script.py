#!/usr/bin/python
# -*- coding: utf-8 -*-


__doc__ = "Toggle the EnneadTab MCP Server on or off. When running, Claude Code can query and control this Revit session via MCP protocol. Requires pyRevit Routes to be enabled."
__title__ = "MCP\nServer"


import os
import subprocess
import signal

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, DATA_FILE


STATE_KEY = "mcp_server_state"
DETACHED_PROCESS = 0x00000008


def find_python3():
    """Try to locate a Python 3 interpreter on this machine."""
    for cmd in ["python", "python3", "py"]:
        try:
            result = subprocess.check_output(
                [cmd, "--version"],
                stderr=subprocess.STDOUT
            )
            if "Python 3" in result.decode("utf-8", errors="replace"):
                return cmd
        except Exception:
            continue
    return None


def check_dependencies(python_cmd):
    """Return True if fastmcp and httpx are importable."""
    try:
        subprocess.check_call(
            [python_cmd, "-c", "import fastmcp; import httpx; print(1)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except Exception:
        return False


def install_dependencies(python_cmd):
    """Install MCP server dependencies from requirements.txt."""
    mcp_dir = get_mcp_server_dir()
    if not mcp_dir:
        return False
    req_file = os.path.join(mcp_dir, "requirements.txt")
    if not os.path.isfile(req_file):
        return False
    try:
        subprocess.check_call(
            [python_cmd, "-m", "pip", "install", "-r", req_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        return True
    except Exception:
        return False


def get_mcp_server_dir():
    """Walk up from this file to find Apps/_engine/mcp_server."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        candidate = os.path.join(current, "Apps", "_engine", "mcp_server")
        if os.path.isdir(candidate):
            return candidate
        current = os.path.dirname(current)
    return ""


def is_process_alive(pid):
    """Check whether a process with the given PID is still running."""
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def check_pyrevit_routes():
    """Check whether pyRevit Routes is reachable on localhost:48884."""
    import urllib2  # pyright: ignore
    try:
        urllib2.urlopen("http://localhost:48884/", timeout=3)
        return True
    except Exception:
        return False


def get_state():
    """Load saved MCP server state."""
    data = DATA_FILE.get_data(STATE_KEY)
    if data is None:
        return {}
    return data


def set_state(data):
    """Persist MCP server state."""
    DATA_FILE.set_data(data, STATE_KEY)


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def mcp_server():
    state = get_state()
    pid = state.get("pid")

    # If already running, stop it
    if pid and is_process_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
        set_state({"pid": None, "running": False})
        NOTIFICATION.messenger("MCP Server stopped.")
        return

    # Find Python 3
    python_cmd = find_python3()
    if not python_cmd:
        NOTIFICATION.messenger(
            "Python 3 is required for the MCP Server.\n"
            "Install from https://python.org"
        )
        return

    # Check / install dependencies
    if not check_dependencies(python_cmd):
        NOTIFICATION.messenger("Installing MCP Server dependencies...")
        if not install_dependencies(python_cmd):
            NOTIFICATION.messenger(
                "Failed to install MCP Server dependencies.\n"
                "Try manually: pip install fastmcp httpx"
            )
            return

    # Check pyRevit Routes
    if not check_pyrevit_routes():
        NOTIFICATION.messenger(
            "pyRevit Routes is not responding on port 48884.\n"
            "Make sure pyRevit is loaded and Routes are enabled.\n"
            "Restart Revit if needed."
        )
        return

    # Launch the MCP server as a detached process
    mcp_dir = get_mcp_server_dir()
    if not mcp_dir:
        NOTIFICATION.messenger("MCP Server directory not found.")
        return

    engine_dir = os.path.dirname(mcp_dir)
    try:
        proc = subprocess.Popen(
            [python_cmd, "-m", "mcp_server", "--app", "revit"],
            cwd=engine_dir,
            creationflags=DETACHED_PROCESS,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        set_state({"pid": proc.pid, "running": True})
        NOTIFICATION.messenger(
            "MCP Server started (PID {}).\n\n"
            "To connect Claude Code, add to claude_desktop_config.json:\n"
            '{{\n'
            '  "mcpServers": {{\n'
            '    "enneadtab-revit": {{\n'
            '      "command": "{}",\n'
            '      "args": ["-m", "mcp_server", "--app", "revit"],\n'
            '      "cwd": "{}"\n'
            '    }}\n'
            '  }}\n'
            '}}'.format(
                proc.pid,
                python_cmd,
                engine_dir.replace("\\", "/")
            )
        )
    except Exception as e:
        NOTIFICATION.messenger(
            "Failed to start MCP Server:\n{}".format(str(e))
        )


if __name__ == "__main__":
    mcp_server()
