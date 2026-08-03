# -*- coding: utf-8 -*-
"""EnneadTab depot client -- shared assets and state over HTTPS.

Replaces the retired office network drives (L:/J:/I:/W:). Shared data is served
through the enneadtab.com depot; this package is the client half. See
docs/plans/2026-07-29-network-drive-retirement-epic.md.

Layout (built across staged commits):
    ROUTES       endpoint constants + URL builders (the contract)   [Commit 1]
    _transport   .NET / urllib dual HTTP + download-to-file          [Commit 2]
    _cache       cache index, atomic replace, sha256, LRU prune      [Commit 2]
    ASSET        manifest + get_asset_path / get_asset_folder        [Commit 2]
    STATE        read_state / write_state / update_state + outbox     [Commit 3]

Design rules (do not violate):
  * Fully-qualified imports inside this subpackage -- always
    "from EnneadTab import X", never bare "import X". The bare form resolves in
    an editor and raises "No module named X" at runtime under the package path
    (this exact bug broke the Rhino AI Render button on 2026-04-21).
  * IronPython 2.7 safe: no f-strings, no type hints, no pathlib. This is the
    one package both the Rhino/Revit IronPython 2.7 runtime and Rhino 8 CPython
    share, so a Py3-only construct will not surface under CPython testing.
  * Safe to ship before the server exists: an unreachable depot is treated
    exactly like being offline -- cached copies serve, uncached reads return
    None with a single rate-limited alarm, nothing raises out of a button.

Commit 1 is additive scaffolding: only ROUTES is real; nothing imports this
package yet, and the repo must still import cleanly.
"""

# Public re-exports. Grows as later commits land (STATE in Commit 3).
# Fully-qualified per the rule above.
from EnneadTab.DEPOT import ROUTES  # noqa: F401
from EnneadTab.DEPOT import ASSET  # noqa: F401
from EnneadTab.DEPOT import STATE  # noqa: F401
from EnneadTab.DEPOT.ASSET import get_asset_path, get_asset_folder, get_manifest  # noqa: F401
from EnneadTab.DEPOT.STATE import read_state, write_state, update_state, list_state, flush_outbox  # noqa: F401

__all__ = [
    "ROUTES", "ASSET", "STATE",
    "get_asset_path", "get_asset_folder", "get_manifest",
    "read_state", "write_state", "update_state", "list_state", "flush_outbox",
]
