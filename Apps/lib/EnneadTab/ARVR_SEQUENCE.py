# -*- coding: utf-8 -*-
"""Exploded-axon / construction-sequence manifest for EnneadTab-ARVR.

The web viewers can pull a model apart (EXPLODE) and reveal it step by step
(BUILD). The steps come from an optional sidecar manifest per room
(EnneadTab-ARVR lib/sequence.ts):

    {"version": 1, "source": "rhino-layers",
     "groups": [{"name": "Level 1", "match": ["Level 1", "Site::Level 1"]}, ...],
     "explode": {"distance": 1.0}}

Groups run bottom to top (explode order) and first to last (build order). A
group's `match` names are compared, case-insensitively and exactly, with the
model's mesh and ancestor node names. Which node names a given exporter writes
is not controlled here; with no usable match the viewer falls back to the
model's own top-level parts, so a manifest never makes things worse.

Pure Python 2.7 / 3.
"""

MAX_GROUPS = 100
MAX_NAME = 80
MAX_MATCHES = 200


def leaf_name(layer_path):
    """'Building::Level 2' -> 'Level 2' (Rhino separates parent and child layers with '::')."""
    return layer_path.split("::")[-1].strip()


def order_by_elevation(layers):
    """Sort [(layer_name, center_z)] bottom to top; ties keep the given order. Returns names."""
    indexed = [(z, i, name) for i, (name, z) in enumerate(layers)]
    indexed.sort(key=lambda t: (t[0], t[1]))
    return [name for _, _, name in indexed]


def build_manifest(ordered_layers, explode_distance=1.0, source="rhino-layers"):
    """Manifest dict from layer names already in the wanted order. Raises ValueError on bad input."""
    if not ordered_layers:
        raise ValueError("Pick at least one layer.")
    if len(ordered_layers) > MAX_GROUPS:
        raise ValueError("At most {} layers per sequence.".format(MAX_GROUPS))
    if not (0 < explode_distance <= 10):
        raise ValueError("Explode distance must be between 0 and 10.")
    groups = []
    for full in ordered_layers:
        leaf = leaf_name(full)
        name = leaf[:MAX_NAME]
        if not name:
            raise ValueError("Layer '{}' has an empty name.".format(full))
        match = [leaf]
        if full.strip() != leaf:
            match.append(full.strip())
        groups.append({"name": name, "match": [m[:MAX_NAME] for m in match][:MAX_MATCHES]})
    return {
        "version": 1,
        "source": source,
        "groups": groups,
        "explode": {"distance": float(explode_distance)},
    }
