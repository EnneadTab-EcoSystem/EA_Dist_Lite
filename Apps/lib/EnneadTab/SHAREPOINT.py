# -*- coding: utf-8 -*-
"""Per-user SharePoint project-file resolver (network-drive retirement, D4 / plan 5.5).

The office project drives (J:/I:/W:) were retired; project files moved to a
SharePoint library that each user syncs to their OWN local folder -- the path
differs per machine (e.g. %USERPROFILE%\\Ennead Architects\\<lib> - Documents\\...).
So this is NOT a depot concern (no HTTP, no auth, no cache): it is a plain local
filesystem resolution through one per-user config, with a first-use folder-picker
prompt when the config is missing or stale.

Reuses the shared_root.json pattern: config lives at
ENVIRONMENT.USER_SHAREPOINT_ROOT_CONFIG. Never silently falls back to a drive
letter -- if the root is unknown, tools get None (or an actionable error) and the
user is prompted once to point at their synced folder.

IronPython 2.7 + CPython safe; fully-qualified imports.
"""

import os
import json

from EnneadTab import ENVIRONMENT


class ProjectRootNotSet(Exception):
    """Raised by get_project_file(required=True) when no SharePoint root is set."""
    pass


def _config_path():
    return ENVIRONMENT.USER_SHAREPOINT_ROOT_CONFIG


def _read_config():
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        f = open(path, "r")
        try:
            data = json.load(f)
        finally:
            f.close()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _write_config(cfg):
    path = _config_path()
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        try:
            os.makedirs(d)
        except Exception:
            pass
    tmp = path + ".part"
    try:
        f = open(tmp, "w")
        try:
            json.dump(cfg, f)
        finally:
            f.close()
        if os.path.exists(path):
            os.remove(path)
        os.rename(tmp, path)
        return True
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        return False


def set_project_root(path):
    """Persist the user's local SharePoint sync root. Returns True on success."""
    cfg = _read_config()
    cfg["root"] = path
    return _write_config(cfg)


def get_project_root(prompt_if_missing=True):
    """Resolve the user's local SharePoint sync root.

    Returns the stored root if it exists on disk. If it is unset or no longer
    present and prompt_if_missing is True, prompts the user (once) to pick it and
    persists the choice. Returns None if still unresolved. NEVER returns a drive
    letter fallback."""
    cfg = _read_config()
    root = cfg.get("root")
    if root and os.path.isdir(root):
        return root
    if prompt_if_missing:
        picked = _prompt_for_root()
        if picked and os.path.isdir(picked):
            set_project_root(picked)
            return picked
    return None


def get_project_file(subpath, required=False, prompt_if_missing=True):
    """Resolve a project-relative path (e.g. "2534/Model/x.xlsx" or a list of
    segments) under the user's SharePoint root. Returns the joined absolute path,
    or None when the root is unknown. Raises ProjectRootNotSet if required=True."""
    root = get_project_root(prompt_if_missing=prompt_if_missing)
    if not root:
        if required:
            raise ProjectRootNotSet(
                "SharePoint project folder is not set. Point EnneadTab at your "
                "synced SharePoint folder to open project files.")
        return None
    if isinstance(subpath, (list, tuple)):
        parts = [p for p in subpath if p not in ("", ".", "..")]
    else:
        parts = [p for p in str(subpath).replace("\\", "/").split("/")
                 if p not in ("", ".", "..")]
    return os.path.join(root, *parts)


def _prompt_for_root():
    """Ask the user to browse to their synced SharePoint folder. Guarded, lazy
    .NET dialog (Revit/Rhino); returns None headless or on any failure -- never
    raises."""
    try:
        import clr  # pyright: ignore
        clr.AddReference("System.Windows.Forms")
        from System.Windows.Forms import FolderBrowserDialog, DialogResult  # pyright: ignore
        dlg = FolderBrowserDialog()
        dlg.Description = ("Select your local synced SharePoint folder "
                           "(the office project drives J:/I:/W: are retired).")
        if dlg.ShowDialog() == DialogResult.OK:
            return dlg.SelectedPath
    except Exception:
        pass
    return None
