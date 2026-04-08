#!/usr/bin/python
# -*- coding: utf-8 -*-


__title__ = "MCPServer"
__doc__ = "Start the EnneadTab MCP Server for Rhino. When running, Claude Code can query and control this Rhino session via MCP protocol."


import os
import rhinoscriptsyntax as rs  # pyright: ignore
import scriptcontext as sc  # pyright: ignore


def find_python3():
    """Try to locate a Python 3 interpreter on this machine."""
    import subprocess
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


def get_mcp_server_dir():
    """Walk up from this file to find Apps/_engine/mcp_server."""
    current = os.path.dirname(os.path.abspath(__file__))
    for _ in range(10):
        candidate = os.path.join(current, "Apps", "_engine", "mcp_server")
        if os.path.isdir(candidate):
            return candidate
        current = os.path.dirname(current)
    return ""


def toggle_server():
    is_running = sc.sticky.get("mcp_rpc_running", False)

    if is_running:
        import rhino_rpc_server
        rhino_rpc_server.stop_server()
        sc.sticky["mcp_rpc_running"] = False
        rs.MessageBox("MCP RPC Server stopped.", 0, "MCP Server")
    else:
        python_cmd = find_python3()
        if not python_cmd:
            rs.MessageBox(
                "Python 3 is required for MCP Server.\n"
                "Install from python.org",
                0,
                "MCP Server"
            )
            return

        mcp_dir = get_mcp_server_dir()
        if not mcp_dir:
            rs.MessageBox(
                "MCP Server directory not found.",
                0,
                "MCP Server"
            )
            return

        import rhino_rpc_server
        rhino_rpc_server.start_server()
        sc.sticky["mcp_rpc_running"] = True

        engine_dir = os.path.dirname(mcp_dir)
        rs.MessageBox(
            "Rhino RPC Server started on localhost:48885.\n\n"
            "Add to ~/.claude.json:\n"
            '{{\n'
            '  "mcpServers": {{\n'
            '    "enneadtab-rhino": {{\n'
            '      "command": "python",\n'
            '      "args": ["-m", "mcp_server", "--app", "rhino"],\n'
            '      "cwd": "{}"\n'
            '    }}\n'
            '  }}\n'
            '}}'.format(engine_dir.replace("\\", "/")),
            0,
            "MCP Server"
        )


if __name__ == "__main__":
    toggle_server()
