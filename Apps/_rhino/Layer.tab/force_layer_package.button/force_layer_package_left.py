__title__ = "ForceLayerPackage"
__doc__ = """Detach selected geometry and blocks to a chosen SYSTEM_ layer.

Workflow:
1. Detect or create SYSTEM_XX root layers.
2. Ask user to choose the target SYSTEM_ layer through a list-box.
3. Migrate non-block geometry first, preserving any sub-layer structure.
4. Make each block definition in the selection unique so that edits do not
   affect instances outside the selection.
5. Update every object (including objects inside the new block definitions)
   so that their layers live under the chosen SYSTEM_ layer.

The implementation is written as a group of small helper functions for
future reuse."""

# ---- Resolve EnneadTab import regardless of Rhino search paths ----
import os
import sys

try:
    import EnneadTab  # noqa: F401
except ImportError:
    _root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
    lib_path = os.path.join(_root, "Apps", "lib")
    if lib_path not in sys.path:
        sys.path.append(lib_path)
    try:
        import EnneadTab  # noqa: F401
    except ImportError:
        raise

import rhinoscriptsyntax as rs
import scriptcontext as sc  # noqa: F401  (needed by Rhino)
import re

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION


# --------------------------------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------------------------------



SYSTEM_LAYER_PREFIX = "SYSTEM_"

def _ensure_system_layers_exist():
    """Return a list of root SYSTEM_ layers that exist in the document.

    If none are found, create three sample layers: SYSTEM_01/02/03.
    """

    layer_names = rs.LayerNames() or []

    def _get_root(name):
        """Return the root portion of a layer path."""
        return name.split("::")[0] if "::" in name else name

    all_root_layers = [_get_root(layer) for layer in layer_names]
    system_layers = sorted(list({l for l in all_root_layers if l.startswith(SYSTEM_LAYER_PREFIX)}))

    if not system_layers:
        for i in range(1, 21):
            layer_name = "{}{:02d}".format(SYSTEM_LAYER_PREFIX, i)
            if not rs.IsLayer(layer_name):
                rs.AddLayer(layer_name)
            system_layers.append(layer_name)

    return system_layers


def _choose_system_layer(system_layers):
    """Display a list-box for the user to pick a SYSTEM_ layer."""

    return rs.ListBox(system_layers, "Pick a SYSTEM layer to attach objects to", __title__)


def _compute_target_layer(current_layer, target_system_layer):
    """Given an object's current layer return the new layer path inside *target_system_layer*.

    Examples
    --------
    >>> _compute_target_layer("SYSTEM_02::Walls::Glass", "SYSTEM_03")
    'SYSTEM_03::Walls::Glass'

    >>> _compute_target_layer("OTHER THING::SYSTEM_02::Walls::Glass", "SYSTEM_04")
    'SYSTEM_04::OTHER THING::Walls::Glass'

    >>> _compute_target_layer("Facade::Glass", "SYSTEM_01")
    'SYSTEM_01::Facade::Glass'

    >>> _compute_target_layer("Wall", "SYSTEM_03")
    'SYSTEM_03::Wall'

    >>> _compute_target_layer(None, "SYSTEM_03")
    raise ValueError("Current layer is None")
    """

    if current_layer is None:
        raise ValueError("Current layer is None")

    parts = current_layer.split("::")

    for idx, part in enumerate(parts):
        if part.startswith(SYSTEM_LAYER_PREFIX):
            pre = parts[:idx]      # segments before the SYSTEM_ occurrence
            post = parts[idx + 1:] # segments after the SYSTEM_ occurrence
            new_parts = [target_system_layer] + pre + post
            new_layer = "::".join(new_parts)
            break
    else:
        # No SYSTEM_ segment found – prepend the target system layer.
        new_layer = "{}::{}".format(target_system_layer, current_layer)

    # Guarantee the layer exists and mimic color/material from current layer when newly created.
    new_layer_pre_exists = rs.IsLayer(new_layer)
    if not new_layer_pre_exists:
        rs.AddLayer(new_layer)

    # Copy appearance if original layer is valid and different.
    if rs.IsLayer(current_layer) and new_layer != current_layer:
        try:
            rs.LayerColor(new_layer, rs.LayerColor(current_layer))
            rs.LayerMaterialIndex(new_layer, rs.LayerMaterialIndex(current_layer))
        except Exception:
            # Safeguard against potential issues (e.g., read-only layers)
            print ("Failed to copy appearance from current layer [{}] to new layer [{}]".format(current_layer, new_layer))
            pass

    return new_layer


def _reattach_object_layer(obj_id, target_system_layer):
    """Move *obj_id* onto the corresponding layer inside *target_system_layer*."""

    current_layer = rs.ObjectLayer(obj_id)
    new_layer = _compute_target_layer(current_layer, target_system_layer)
    if new_layer != current_layer:
        rs.ObjectLayer(obj_id, layer=new_layer)


# --------------------------------------------------------------------------------------
# Block utilities
# --------------------------------------------------------------------------------------


def _strip_system_tag(name):
    """Remove any SYSTEM_XY prefix or infix from *name* (case-sensitive)."""

    # Remove every occurrence of SYSTEM_XX and any adjacent underscores.
    pattern = re.compile(r"_?SYSTEM_\d{2}_?", flags=re.IGNORECASE)
    cleaned = re.sub(pattern, "_", name)
    # Collapse multiple underscores that may result from replacements.
    cleaned = re.sub(r"__+", "_", cleaned)
    return cleaned.strip("_")


def _generate_unique_block_name(base_name, target_system_layer):
    """Return a unique block name incorporating *target_system_layer*.

    Steps:
    1. Remove existing SYSTEM_XX tokens from *base_name*.
    2. Append the new system layer name.
    3. If a conflict exists, append `_new` until the name is unique.
    """

    clean_base = _strip_system_tag(base_name)

    tentative = "{}_{}".format(clean_base, target_system_layer)
    while tentative in rs.BlockNames():
        tentative += "_new"
    return tentative


def _make_blocks_unique_in_selection(block_objs, target_system_layer):
    """Ensure each block definition in *block_objs* is unique for the selection.

    After creating unique definitions, replace the selected instances so that they
    reference the new definition.
    """

    # Group selected instances by their current definition name
    by_definition = {}
    for inst in block_objs:
        def_name = rs.BlockInstanceName(inst)
        by_definition.setdefault(def_name, []).append(inst)

    for def_name, instances in by_definition.items():

        # Build a unique block name based on target system layer
        new_block_name = _generate_unique_block_name(def_name, target_system_layer)

        # Select the chosen instances and run Rhino's native command to make them unique
        rs.UnselectAllObjects()
        rs.SelectObjects(instances)
        rs.Command("_-CreateUniqueBlock \"{}\" _Enter".format(new_block_name), False)
        rs.UnselectAllObjects()

        # After creation, migrate layers for the new block definition
        _migrate_block_definition_layers(new_block_name, target_system_layer)


# --------------------------------------------------------------------------------------
# Duplicate nested definitions when they are shared across documents
# --------------------------------------------------------------------------------------


def _duplicate_block_definition(def_name, target_system_layer, processed_defs, mapping):
    """Create a brand-new block definition copied from *def_name*.

    Returns the new definition name and registers it in *mapping*.
    """

    if def_name in mapping:
        return mapping[def_name]

    new_def_name = _generate_unique_block_name(def_name, target_system_layer)

    # Insert a temporary instance of the old definition and explode it to copy contents.
    temp_inst = rs.InsertBlock(def_name, (0, 0, 0))
    if temp_inst is None:
        # Fallback: just reuse original definition
        mapping[def_name] = def_name
        return def_name

    parts = rs.ExplodeBlockInstance(temp_inst, explode_nested_instances=False)

    # Process each part: ensure nested definitions are also duplicated and layers migrated
    new_parts = []
    for part in parts:
        if rs.IsBlockInstance(part):
            nested_original = rs.BlockInstanceName(part)
            nested_unique = _duplicate_block_definition(nested_original, target_system_layer, processed_defs, mapping)
            xform = rs.BlockInstanceXform(part)
            rs.DeleteObject(part)
            new_part = rs.InsertBlock2(nested_unique, xform)
            _reattach_object_layer(new_part, target_system_layer)
            new_parts.append(new_part)
        else:
            _reattach_object_layer(part, target_system_layer)
            new_parts.append(part)

    rs.AddBlock(new_parts, (0, 0, 0), name=new_def_name, delete_input=True)
    mapping[def_name] = new_def_name
    return new_def_name


def _migrate_block_definition_layers(block_name, target_system_layer, processed=None, mapping=None):
    """Recursively migrate layers and break shared nested definitions.

    *mapping* keeps track of already duplicated definitions so we reuse them
    within the same system hierarchy.
    """

    if processed is None:
        processed = set()
    if mapping is None:
        mapping = {}

    if block_name in processed:
        return
    processed.add(block_name)

    contents = rs.BlockObjects(block_name)
    if not contents:
        return

    _process_objects(contents, target_system_layer, processed, mapping)


# --------------------------------------------------------------------------------------
# Generic object processing helper (re-used by main & nested migration)
# --------------------------------------------------------------------------------------


def _process_objects(object_ids, target_system_layer, processed_defs, mapping):
    """Process a list of Rhino objects for layer migration & block duplication.

    Parameters
    ----------
    object_ids : list[str]
        Objects (geometry or block instances) to process.
    target_system_layer : str
        The SYSTEM_ layer into which everything will be migrated.
    processed_defs : set[str]
        Keeps track of block definitions we've already walked.
    mapping : dict[str, str]
        Maps original definition names to their duplicated counterparts.
    """

    if not object_ids:
        return

    inner_blocks = [obj for obj in object_ids if rs.IsBlockInstance(obj)]
    inner_non_blocks = [obj for obj in object_ids if not rs.IsBlockInstance(obj)]

    # First handle block instances
    for obj in inner_blocks:
        nested_def = rs.BlockInstanceName(obj)

        # If definition is shared (multiple instances globally), duplicate it for this system
        is_shared = rs.BlockInstanceCount(nested_def) > 1

        if is_shared:
            unique_nested_def = _duplicate_block_definition(nested_def, target_system_layer, processed_defs, mapping)
            xform = rs.BlockInstanceXform(obj)
            rs.DeleteObject(obj)
            new_inst = rs.InsertBlock2(unique_nested_def, xform)
            obj = new_inst  # replace reference

        # Recurse into nested definition (unique or originally single-use)
        updated_def = rs.BlockInstanceName(obj)
        _migrate_block_definition_layers(updated_def, target_system_layer, processed_defs, mapping)

        _reattach_object_layer(obj, target_system_layer)

    # Now treat simple geometry
    for obj in inner_non_blocks:
        _reattach_object_layer(obj, target_system_layer)


# --------------------------------------------------------------------------------------
# Main command
# --------------------------------------------------------------------------------------


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def force_layer_package():
    """Entrypoint for the button."""

    # 1. Gather selection
    selection = rs.GetObjects("Select objects to migrate under SYSTEM layer", preselect=True)
    if not selection:
        NOTIFICATION.messenger("Nothing selected - command cancelled.")
        return

    rs.EnableRedraw(False)

    # 2. Prepare SYSTEM layers and ask user which one to use
    system_layers = _ensure_system_layers_exist()
    target_system_layer = _choose_system_layer(system_layers)
    if not target_system_layer:
        NOTIFICATION.messenger("No system layer chosen - command cancelled.")
        return

    # 3. Process all selected objects with unified logic
    processed_defs = set()
    mapping = {}
    _process_objects(selection, target_system_layer, processed_defs, mapping)

    rs.EnableRedraw(True)
    NOTIFICATION.messenger("Selection migrated under {}.".format(target_system_layer))


if __name__ == "__main__":
    force_layer_package()
