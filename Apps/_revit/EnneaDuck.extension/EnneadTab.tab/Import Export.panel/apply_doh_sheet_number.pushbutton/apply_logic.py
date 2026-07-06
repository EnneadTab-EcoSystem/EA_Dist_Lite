# -*- coding: utf-8 -*-
"""Pure (Revit-free) logic for the Apply DOH SheetNum button.
Dual-safe for IronPython 2.7 and CPython 3.x: no f-strings, no type hints,
no reliance on dict/set iteration order."""
from collections import namedtuple

SheetRow = namedtuple(
    "SheetRow",
    ["sheet_id", "live", "internal", "doh", "is_placeholder", "is_changable"],
)

MODE_INTERNAL = "INTERNAL"
MODE_DOH = "DOH"
MODE_IDENTICAL = "IDENTICAL"
MODE_DRIFT = "DRIFT"
MODE_MIXED = "MIXED"
MODE_EMPTY = "EMPTY"

SOURCE_INTERNAL = "internal"
SOURCE_DOH = "doh"

TEMP_PREFIX = "__APPLY_TMP__"


def is_empty(value):
    return value is None or value == ""


def _source_value(row, source):
    return row.internal if source == SOURCE_INTERNAL else row.doh


def classify(row):
    """Return 'P','Q','G','N' for a row whose internal AND doh are non-empty."""
    if is_empty(row.internal) or is_empty(row.doh):
        raise ValueError("classify() requires both stores populated")
    li = row.live == row.internal
    ld = row.live == row.doh
    if li and ld:
        return "G"
    if li:
        return "P"
    if ld:
        return "Q"
    return "N"


def infer_mode(rows):
    classifiable = [r for r in rows
                    if not is_empty(r.internal) and not is_empty(r.doh)]
    if not classifiable:
        return MODE_EMPTY
    classes = set(classify(r) for r in classifiable)
    if classes == set(["G"]):
        return MODE_IDENTICAL
    if "N" in classes:
        return MODE_DRIFT
    has_p = "P" in classes
    has_q = "Q" in classes
    if has_p and has_q:
        return MODE_MIXED
    if has_q:
        return MODE_DOH
    return MODE_INTERNAL


def find_incomplete(rows):
    return [r.sheet_id for r in rows
            if not r.is_placeholder and (is_empty(r.internal) or is_empty(r.doh))]


def find_duplicates(rows, source):
    buckets = {}
    for r in rows:
        v = _source_value(r, source)
        if is_empty(v):
            continue
        buckets.setdefault(v, []).append(r.sheet_id)
    out = {}
    for v, ids in buckets.items():
        if len(ids) > 1:
            out[v] = ids
    return out


def find_collisions(rows, source, reserved_numbers):
    reserved = set(reserved_numbers)
    hits = []
    for r in rows:
        if r.is_placeholder:
            continue
        v = _source_value(r, source)
        if is_empty(v):
            continue
        if v in reserved:
            hits.append((r.sheet_id, v))
    return hits


def find_non_changable(rows):
    return [r.sheet_id for r in rows if not r.is_changable]


def make_temp_tokens(sheet_ids, run_guid):
    tokens = {}
    i = 0
    for sid in sheet_ids:
        tokens[sid] = TEMP_PREFIX + str(run_guid) + "__" + str(i)
        i += 1
    return tokens


def temp_prefix_collision(rows, run_guid):
    prefix = TEMP_PREFIX + str(run_guid) + "__"
    for r in rows:
        if r.live is not None and r.live.startswith(prefix):
            return True
    return False


def plan_apply(rows, target):
    written = [r for r in rows if not r.is_placeholder]
    finals = []
    changed = False
    for r in written:
        v = _source_value(r, target)
        finals.append((r.sheet_id, v))
        if r.live != v:
            changed = True
    if not changed:
        return ("noop", [])
    return ("apply", finals)


def plan_capture(rows, mode):
    if mode == MODE_DOH:
        return ("refused",
                "Model is in DOH mode; capturing now would overwrite "
                "Sheet Number_Internal with DOH numbers.")
    targets = []
    for r in rows:
        if r.is_placeholder:
            continue
        if is_empty(r.internal):
            targets.append((r.sheet_id, r.live))
        elif not is_empty(r.doh) and classify(r) == "N":
            targets.append((r.sheet_id, r.live))
    return ("capture", targets)


def plan_fill_doh(rows):
    out = []
    for r in rows:
        if is_empty(r.doh) and not is_empty(r.internal):
            out.append((r.sheet_id, r.internal))
    return out
