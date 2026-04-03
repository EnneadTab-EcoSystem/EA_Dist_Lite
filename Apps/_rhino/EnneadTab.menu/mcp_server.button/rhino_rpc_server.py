# -*- coding: utf-8 -*-
"""Rhino HTTP RPC Server — exposes Rhino API over localhost:48885.

This module runs INSIDE Rhino via IronPython 2.7.  It provides start_server()
and stop_server() to manage a System.Net.HttpListener on a background thread.
All Rhino API calls are marshaled to the main thread via
Rhino.RhinoApp.InvokeOnUiThread().

Usage:
    import rhino_rpc_server
    rhino_rpc_server.start_server()   # non-blocking
    # ... later ...
    rhino_rpc_server.stop_server()
"""

import System  # pyright: ignore
from System.Net import HttpListener  # pyright: ignore
from System.Threading import Thread, ThreadStart  # pyright: ignore
from System.IO import StreamReader  # pyright: ignore
import Rhino  # pyright: ignore
import rhinoscriptsyntax as rs  # pyright: ignore
import scriptcontext as sc  # pyright: ignore
import json
import os
import sys
import traceback

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------
_listener = None
_thread = None
_running = False

PORT = 48885


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_server():
    """Start the HTTP listener on a background thread."""
    global _listener, _thread, _running
    if _running:
        return "Server already running on port {}".format(PORT)

    _listener = HttpListener()
    _listener.Prefixes.Add("http://localhost:{}/".format(PORT))
    _listener.Start()
    _running = True

    _thread = Thread(ThreadStart(_listen_loop))
    _thread.IsBackground = True
    _thread.Start()
    return "Server started on http://localhost:{}/".format(PORT)


def stop_server():
    """Stop the HTTP listener and background thread."""
    global _running, _listener, _thread
    _running = False
    if _listener:
        try:
            _listener.Stop()
            _listener.Close()
        except Exception:
            pass
        _listener = None
    _thread = None
    return "Server stopped."


# ---------------------------------------------------------------------------
# Listener loop (runs on background thread)
# ---------------------------------------------------------------------------

def _listen_loop():
    """Block on GetContext() and dispatch each request."""
    while _running:
        try:
            context = _listener.GetContext()
            _handle_request(context)
        except Exception:
            if _running:
                continue


# ---------------------------------------------------------------------------
# Request dispatcher
# ---------------------------------------------------------------------------

def _handle_request(context):
    """Parse the HTTP request, marshal to UI thread, return JSON."""
    request = context.Request
    response = context.Response

    path = request.Url.AbsolutePath.rstrip("/")
    method = request.HttpMethod

    # Read body for POST requests
    body = ""
    if method == "POST":
        reader = StreamReader(request.InputStream, request.ContentEncoding)
        body = reader.ReadToEnd()
        reader.Close()

    # Parse query string params into a dict
    query = {}
    qs = request.Url.Query
    if qs and qs.startswith("?"):
        for part in qs[1:].split("&"):
            if "=" in part:
                k, v = part.split("=", 1)
                query[k] = v

    result = {"error": "Internal error"}
    status = 500

    try:
        # Use a mutable list to pass results out of the closure
        result_holder = [None, 200]

        def do_on_ui():
            try:
                r, s = _route(path, method, body, query)
                result_holder[0] = r
                result_holder[1] = s
            except Exception:
                result_holder[0] = {"error": traceback.format_exc()}
                result_holder[1] = 500

        Rhino.RhinoApp.InvokeOnUiThread(System.Action(do_on_ui))

        result = result_holder[0]
        status = result_holder[1]
    except Exception as e:
        result = {"error": str(e)}
        status = 500

    # Add CORS headers for local dev
    response.AddHeader("Access-Control-Allow-Origin", "*")
    response.AddHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    response.AddHeader("Access-Control-Allow-Headers", "Content-Type")

    if method == "OPTIONS":
        response.StatusCode = 204
        response.ContentLength64 = 0
        response.OutputStream.Close()
        return

    # Send JSON response
    response_body = json.dumps(result, default=str)
    response_bytes = System.Text.Encoding.UTF8.GetBytes(response_body)
    response.StatusCode = status
    response.ContentType = "application/json; charset=utf-8"
    response.ContentLength64 = response_bytes.Length
    response.OutputStream.Write(response_bytes, 0, response_bytes.Length)
    response.OutputStream.Close()


# ---------------------------------------------------------------------------
# Router — runs on Rhino's main (UI) thread
# ---------------------------------------------------------------------------

def _route(path, method, body, query):
    """Route the request to the appropriate handler.

    Returns (result_dict, status_code).
    """
    data = {}
    if body:
        try:
            data = json.loads(body)
        except Exception:
            pass

    # Merge query params into data (query params are lower priority)
    merged = dict(query)
    merged.update(data)

    # Parse path segments: /enneadtab/status -> ["enneadtab", "status"]
    segments = [s for s in path.split("/") if s]

    if len(segments) < 2 or segments[0] != "enneadtab":
        return {"error": "Unknown route: {}".format(path)}, 404

    route = segments[1]

    # ---- Read-only endpoints ----
    if route == "status":
        return _handle_status(), 200

    if route == "model-info":
        return _handle_model_info(), 200

    if route == "elements":
        return _handle_elements(merged), 200

    if route == "element" and len(segments) >= 4:
        elem_id = segments[2]
        sub = segments[3]
        if sub == "parameters" and method == "GET":
            return _handle_element_params(elem_id), 200
        if sub == "set-parameter" and method == "POST":
            return _handle_set_param(elem_id, merged), 200
        return {"error": "Unknown element sub-route: {}".format(sub)}, 404

    if route == "levels":
        return {"levels": [], "note": "Levels are not applicable in Rhino."}, 200

    if route == "views":
        return _handle_views(), 200

    if route == "families":
        return _handle_block_defs(merged), 200

    if route == "layers":
        return _handle_layers(), 200

    # ---- Write endpoints ----
    if route == "set-layer-state" and method == "POST":
        return _handle_set_layer(merged), 200

    if route == "execute-code" and method == "POST":
        return _handle_execute_code(merged), 200

    if route == "tools":
        return _handle_list_tools(), 200

    if route == "run-tool" and method == "POST":
        return _handle_run_tool(merged), 200

    if route == "view-image":
        return _handle_view_image(merged), 200

    if route == "export-geometry" and method == "POST":
        return _handle_export(merged), 200

    return {"error": "Unknown route: {}".format(path)}, 404


# ---------------------------------------------------------------------------
# Handler implementations
# ---------------------------------------------------------------------------

def _handle_status():
    """GET /enneadtab/status/ — Rhino version, active document info."""
    doc = Rhino.RhinoDoc.ActiveDoc
    return {
        "app": "rhino",
        "version": Rhino.RhinoApp.Version.ToString(),
        "document": doc.Name if doc else None,
        "path": doc.Path if doc else "",
        "server_port": PORT,
    }


def _handle_model_info():
    """GET /enneadtab/model-info/ — file name, path, units, tolerance."""
    doc = Rhino.RhinoDoc.ActiveDoc
    if not doc:
        return {"error": "No document open"}

    return {
        "name": doc.Name,
        "path": doc.Path,
        "units": str(doc.ModelUnitSystem),
        "absolute_tolerance": doc.ModelAbsoluteTolerance,
        "angle_tolerance": doc.ModelAngleToleranceDegrees,
    }


def _handle_elements(data):
    """GET /enneadtab/elements/ — query objects by category type.

    Query param ``category``: Curve, Surface, Brep, Mesh, Point, Block, etc.
    """
    category = data.get("category", "").strip()

    # Map category name to rhinoscriptsyntax filter constant
    filter_map = {
        "point": 1,       # rs.filter.point
        "pointcloud": 2,  # rs.filter.pointcloud
        "curve": 4,       # rs.filter.curve
        "surface": 8,     # rs.filter.surface
        "polysurface": 16,  # rs.filter.polysurface
        "mesh": 32,       # rs.filter.mesh
        "light": 256,     # rs.filter.light
        "annotation": 512,  # rs.filter.annotation
        "block": 4096,    # rs.filter.instance (block instance)
    }

    if category:
        filter_val = filter_map.get(category.lower())
        if filter_val is None:
            return {
                "error": "Unknown category: {}. Valid: {}".format(
                    category, ", ".join(sorted(filter_map.keys()))
                )
            }
        ids = rs.ObjectsByType(filter_val, select=False) or []
    else:
        # Return all visible objects
        ids = rs.AllObjects(select=False) or []

    elements = []
    for obj_id in ids:
        obj_id_str = str(obj_id)
        name = rs.ObjectName(obj_id) or ""
        layer = rs.ObjectLayer(obj_id) or ""
        obj_type = rs.ObjectType(obj_id)
        elements.append({
            "id": obj_id_str,
            "name": name,
            "layer": layer,
            "type": obj_type,
        })

    return {
        "count": len(elements),
        "category_filter": category or "all",
        "elements": elements,
    }


def _handle_element_params(elem_id):
    """GET /enneadtab/element/<id>/parameters/ — object attributes."""
    try:
        guid = System.Guid(elem_id)
    except Exception:
        return {"error": "Invalid GUID: {}".format(elem_id)}

    if not rs.IsObject(guid):
        return {"error": "Object not found: {}".format(elem_id)}

    color = rs.ObjectColor(guid)
    mat_idx = rs.ObjectMaterialIndex(guid)

    return {
        "id": elem_id,
        "name": rs.ObjectName(guid) or "",
        "layer": rs.ObjectLayer(guid) or "",
        "color": [color.R, color.G, color.B] if color else None,
        "material_index": mat_idx,
        "type": rs.ObjectType(guid),
        "visible": rs.IsVisibleInView(guid),
    }


def _handle_set_param(elem_id, data):
    """POST /enneadtab/element/<id>/set-parameter/ — set name, layer, color."""
    try:
        guid = System.Guid(elem_id)
    except Exception:
        return {"error": "Invalid GUID: {}".format(elem_id)}

    if not rs.IsObject(guid):
        return {"error": "Object not found: {}".format(elem_id)}

    changed = []

    if "name" in data:
        rs.ObjectName(guid, data["name"])
        changed.append("name")

    if "layer" in data:
        layer_name = data["layer"]
        if not rs.IsLayer(layer_name):
            return {"error": "Layer does not exist: {}".format(layer_name)}
        rs.ObjectLayer(guid, layer_name)
        changed.append("layer")

    if "color" in data:
        c = data["color"]
        if isinstance(c, list) and len(c) >= 3:
            rs.ObjectColor(guid, (c[0], c[1], c[2]))
            changed.append("color")

    return {"id": elem_id, "changed": changed}


def _handle_views():
    """GET /enneadtab/views/ — list named views."""
    named = rs.NamedViews() or []
    views = []
    for name in named:
        views.append({"name": name})

    # Also list open viewports
    doc = Rhino.RhinoDoc.ActiveDoc
    viewports = []
    if doc:
        for view in doc.Views:
            viewports.append({
                "name": view.ActiveViewport.Name,
                "is_active": (view == doc.Views.ActiveView),
            })

    return {
        "named_views": views,
        "open_viewports": viewports,
    }


def _handle_block_defs(data):
    """GET /enneadtab/families/ — list block definitions (Rhino equivalent)."""
    names = rs.BlockNames(sort=True) or []
    blocks = []
    for name in names:
        count = rs.BlockInstanceCount(name)
        blocks.append({
            "name": name,
            "instance_count": count if count else 0,
        })

    return {
        "count": len(blocks),
        "blocks": blocks,
    }


def _handle_layers():
    """GET /enneadtab/layers/ — list all layers with state."""
    names = rs.LayerNames() or []
    layers = []
    for name in names:
        color = rs.LayerColor(name)
        layers.append({
            "name": name,
            "visible": rs.LayerVisible(name),
            "locked": rs.LayerLocked(name),
            "color": [color.R, color.G, color.B] if color else None,
        })
    return {"count": len(layers), "layers": layers}


def _handle_set_layer(data):
    """POST /enneadtab/set-layer-state/ — toggle visibility/lock/color."""
    layer_name = data.get("layer")
    if not layer_name:
        return {"error": "layer name is required"}

    if not rs.IsLayer(layer_name):
        return {"error": "Layer not found: {}".format(layer_name)}

    changed = []

    if "visible" in data:
        rs.LayerVisible(layer_name, data["visible"])
        changed.append("visible")

    if "locked" in data:
        rs.LayerLocked(layer_name, data["locked"])
        changed.append("locked")

    if "color" in data:
        c = data["color"]
        if isinstance(c, list) and len(c) >= 3:
            rs.LayerColor(layer_name, (c[0], c[1], c[2]))
            changed.append("color")

    return {"layer": layer_name, "changed": changed}


def _handle_execute_code(data):
    """POST /enneadtab/execute-code/ — run Python code in Rhino context.

    Body: {"code": "import rhinoscriptsyntax as rs\\nprint rs.DocumentName()"}
    """
    code = data.get("code", "")
    if not code:
        return {"error": "code is required"}

    # Capture stdout via StringIO
    try:
        from StringIO import StringIO
    except ImportError:
        from io import StringIO

    output_buf = StringIO()
    exec_globals = {
        "rs": rs,
        "sc": sc,
        "Rhino": Rhino,
        "System": System,
        "__builtins__": __builtins__,
    }

    old_stdout = sys.stdout
    try:
        sys.stdout = output_buf
        exec(code, exec_globals)
        stdout_text = output_buf.getvalue()
    except Exception:
        stdout_text = output_buf.getvalue()
        return {
            "success": False,
            "stdout": stdout_text,
            "error": traceback.format_exc(),
        }
    finally:
        sys.stdout = old_stdout

    return {"success": True, "stdout": stdout_text}


def _handle_list_tools():
    """GET /enneadtab/tools/ — scan EnneadTab modules for __mcp_tools__."""
    lib_path = _ensure_lib_on_path()
    if not lib_path:
        return {"module_count": 0, "tool_count": 0, "modules": {}}

    enneadtab_dir = os.path.join(lib_path, "EnneadTab")
    if not os.path.isdir(enneadtab_dir):
        return {"module_count": 0, "tool_count": 0, "modules": {}}

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
            continue

    total = sum(len(v) for v in tools.values())
    return {"module_count": len(tools), "tool_count": total, "modules": tools}


def _handle_run_tool(data):
    """POST /enneadtab/run-tool/ — call an EnneadTab MCP-safe function.

    Body: {"module": "COLOR", "function": "get_random_color", "args": {}}
    """
    module_name = data.get("module")
    function_name = data.get("function")
    args = data.get("args", {})

    if not module_name or not function_name:
        return {"error": "module and function are required"}

    _ensure_lib_on_path()
    full_module_name = "EnneadTab.{}".format(module_name)

    try:
        if full_module_name in sys.modules:
            mod = sys.modules[full_module_name]
        else:
            mod = __import__(full_module_name, fromlist=[module_name])
    except ImportError as e:
        return {"error": "Module not found: {}. {}".format(module_name, str(e))}

    # Verify function is in __mcp_tools__ whitelist
    mcp_tools = getattr(mod, "__mcp_tools__", None)
    if not mcp_tools or function_name not in mcp_tools:
        return {
            "error": "Function '{}' is not in __mcp_tools__ for module '{}'".format(
                function_name, module_name
            )
        }

    func = getattr(mod, function_name, None)
    if func is None or not callable(func):
        return {
            "error": "Function '{}' not found or not callable in module '{}'".format(
                function_name, module_name
            )
        }

    try:
        if isinstance(args, dict):
            result = func(**args)
        elif isinstance(args, (list, tuple)):
            result = func(*args)
        else:
            result = func()
    except Exception:
        return {"error": traceback.format_exc()}

    # Ensure JSON-serializable
    if result is None:
        result = {}
    elif not isinstance(result, (dict, list, str, int, float, bool)):
        result = {"result": str(result)}

    return {
        "module": module_name,
        "function": function_name,
        "success": True,
        "data": result,
    }


def _handle_view_image(data):
    """GET /enneadtab/view-image/ — capture the active viewport as base64 PNG.

    Optional query params: width, height (default 800x600).
    """
    import base64

    doc = Rhino.RhinoDoc.ActiveDoc
    if not doc:
        return {"error": "No document open"}

    view = doc.Views.ActiveView
    if not view:
        return {"error": "No active view"}

    width = int(data.get("width", 800))
    height = int(data.get("height", 600))

    try:
        size = System.Drawing.Size(width, height)
        bitmap = view.CaptureToBitmap(size)
        if bitmap is None:
            return {"error": "CaptureToBitmap returned None"}

        # Save to a MemoryStream, then base64 encode
        ms = System.IO.MemoryStream()
        bitmap.Save(ms, System.Drawing.Imaging.ImageFormat.Png)
        raw_bytes = ms.ToArray()
        ms.Close()
        bitmap.Dispose()

        # Convert .NET byte[] to Python bytes then base64
        py_bytes = bytes(bytearray(raw_bytes))
        b64 = base64.b64encode(py_bytes)

        return {
            "format": "png",
            "width": width,
            "height": height,
            "base64": b64,
        }
    except Exception:
        return {"error": traceback.format_exc()}


def _handle_export(data):
    """POST /enneadtab/export-geometry/ — export objects to file.

    Body: {"format": "obj", "path": "C:/temp/export.obj", "object_ids": [...]}
    Supported formats: 3dm, obj, stl
    """
    fmt = data.get("format", "obj").lower()
    export_path = data.get("path", "")
    object_ids = data.get("object_ids", [])

    if not export_path:
        return {"error": "path is required"}

    supported = ["3dm", "obj", "stl"]
    if fmt not in supported:
        return {"error": "Unsupported format: {}. Use: {}".format(fmt, ", ".join(supported))}

    # Select the requested objects (or all if none specified)
    rs.UnselectAllObjects()
    if object_ids:
        for oid in object_ids:
            try:
                guid = System.Guid(str(oid))
                rs.SelectObject(guid)
            except Exception:
                pass
    else:
        rs.AllObjects(select=True)

    # Use Rhino command-line export (silent)
    # _-Export handles format by file extension
    cmd = '_-Export "{}" _Enter'.format(export_path)
    success = rs.Command(cmd, echo=False)
    rs.UnselectAllObjects()

    if success:
        return {"success": True, "path": export_path, "format": fmt}
    else:
        return {"error": "Export command failed. Check file path and format."}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ensure_lib_on_path():
    """Walk up from this file to find Apps/lib and add it to sys.path."""
    current = os.path.dirname(os.path.abspath(__file__))
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
