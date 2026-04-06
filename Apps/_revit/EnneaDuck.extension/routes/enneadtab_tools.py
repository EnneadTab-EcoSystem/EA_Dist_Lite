# -*- coding: utf-8 -*-
"""EnneadTab tools bridge route handler for EnneadTab MCP.

Discovers and invokes functions from EnneadTab modules that expose
a __mcp_tools__ attribute listing callable function names.
"""
import json
import os
import sys
import traceback

from pyrevit import routes
from Autodesk.Revit import DB


def _ensure_lib_on_path():
    """Walk up from this file to find Apps/lib and add it to sys.path."""
    current = os.path.dirname(os.path.abspath(__file__))
    # Walk up looking for Apps/lib
    for _ in range(10):
        candidate = os.path.join(current, "Apps", "lib")
        if os.path.isdir(candidate):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return None


def _scan_modules():
    """Scan EnneadTab modules for __mcp_tools__ attribute.

    Returns a dict of {module_name: [function_names]}.
    """
    lib_path = _ensure_lib_on_path()
    if lib_path is None:
        return {}

    enneadtab_dir = os.path.join(lib_path, "EnneadTab")
    if not os.path.isdir(enneadtab_dir):
        return {}

    tools = {}
    for filename in os.listdir(enneadtab_dir):
        if not filename.endswith(".py") or filename.startswith("_"):
            continue

        module_name = filename[:-3]
        full_module_name = "EnneadTab.{}".format(module_name)

        try:
            if full_module_name in sys.modules:
                mod = sys.modules[full_module_name]
            else:
                mod = __import__(full_module_name, fromlist=[module_name])

            mcp_tools = getattr(mod, "__mcp_tools__", None)
            if mcp_tools and isinstance(mcp_tools, (list, tuple)):
                tools[module_name] = list(mcp_tools)
        except Exception:
            # Skip modules that fail to import
            continue

    return tools


def register_enneadtab_tools_routes(api):
    @api.route("/tools/", methods=["GET"])
    def list_tools(doc, request):
        tools = _scan_modules()
        total = sum(len(v) for v in tools.values())
        return routes.make_response(data={
            "module_count": len(tools),
            "tool_count": total,
            "modules": tools,
        })

    @api.route("/run-tool/", methods=["POST"])
    def run_tool(doc, request):
        if not doc:
            return routes.make_response(
                data={"error": "No document open"},
                status_code=400,
            )

        data = json.loads(request.data) if isinstance(request.data, str) else request.data
        module_name = data.get("module")
        function_name = data.get("function")
        args = data.get("args", {})

        if not module_name or not function_name:
            return routes.make_response(
                data={"error": "module and function are required"},
                status_code=400,
            )

        _ensure_lib_on_path()

        full_module_name = "EnneadTab.{}".format(module_name)

        try:
            if full_module_name in sys.modules:
                mod = sys.modules[full_module_name]
            else:
                mod = __import__(full_module_name, fromlist=[module_name])
        except ImportError as e:
            return routes.make_response(
                data={"error": "Module not found: {}. {}".format(module_name, str(e))},
                status_code=404,
            )

        # Verify function is in __mcp_tools__ whitelist
        mcp_tools = getattr(mod, "__mcp_tools__", None)
        if not mcp_tools or function_name not in mcp_tools:
            return routes.make_response(
                data={
                    "error": "Function '{}' is not in __mcp_tools__ for module '{}'".format(
                        function_name, module_name
                    )
                },
                status_code=403,
            )

        func = getattr(mod, function_name, None)
        if func is None or not callable(func):
            return routes.make_response(
                data={
                    "error": "Function '{}' not found or not callable in module '{}'".format(
                        function_name, module_name
                    )
                },
                status_code=404,
            )

        transaction_name = "MCP: {}.{}".format(module_name, function_name)
        t = DB.Transaction(doc, transaction_name)
        try:
            t.Start()

            if isinstance(args, dict):
                result = func(doc=doc, **args)
            elif isinstance(args, (list, tuple)):
                result = func(doc, *args)
            else:
                result = func(doc)

            t.Commit()
        except Exception as e:
            if t.HasStarted():
                t.RollBack()
            return routes.make_response(
                data={
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                },
                status_code=500,
            )

        # Ensure result is JSON-serializable
        if result is None:
            result = {}
        elif not isinstance(result, (dict, list, str, int, float, bool)):
            result = {"result": str(result)}

        return routes.make_response(data={
            "module": module_name,
            "function": function_name,
            "success": True,
            "data": result,
        })
