#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "List all Extensible Storage schemas in the current model — both yours (EnneadTab) and from other consultants. Also scans the Revit journal file for hints (schema, add-in, errors)."
__title__ = "Check External Schema"

import io
import os
from datetime import datetime
import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, OUTPUT
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB  # pyright: ignore

DOC = REVIT_APPLICATION.get_doc()


def _schema_names_in_document(doc, schemas):
    """Return set of schema names that have at least one element with that schema in the document.
    API: Schema.GUID (property), ExtensibleStorageFilter(Guid), FilteredElementCollector(doc).WherePasses(filter).GetElementCount().
    """
    result = set()
    for s in schemas:
        try:
            guid = s.GUID  # Schema.GUID property -> System.Guid (revitapidocs)
            filt = DB.ExtensibleStorage.ExtensibleStorageFilter(guid)  # Constructor(GuidschemaGuid)
            count = DB.FilteredElementCollector(doc).WherePasses(filt).GetElementCount()
            if count > 0:
                name = s.SchemaName if s.SchemaName else str(guid)  # Schema.SchemaName property
                result.add(name)
        except Exception:
            continue
    return result


def _schema_element_counts_in_document(doc, schemas):
    """Return dict mapping schema name -> element count for schemas that have at least one element in the document."""
    counts = {}
    for s in schemas:
        try:
            guid = s.GUID
            filt = DB.ExtensibleStorage.ExtensibleStorageFilter(guid)
            count = DB.FilteredElementCollector(doc).WherePasses(filt).GetElementCount()
            if count > 0:
                name = s.SchemaName if s.SchemaName else str(guid)
                counts[name] = count
        except Exception:
            continue
    return counts

# VendorId we consider "ours" (EnneadTab). Any other VendorId = schema from another consultant/vendor.
ENNEAD_VENDOR_ID = "EnneadTab"

# Journal: Application.RecordingJournalFilename = path to current session log (Autodesk / Building Coder).
JOURNAL_HINT_KEYWORDS = [
    "schema", "extensiblestorage", "entity", "vendorid", "vendor",
    "execute_command", "add-in", "addin", "external command",
    "journalcomment", "error", "exception", "fail",
]

# Map schema name substrings to journal search terms (add-in / product names as they appear in journal).
SCHEMA_TO_JOURNAL_KEYWORDS = [
    ("Enscape", "Enscape"),
    ("ExportViewSheet", "ExportViewSheet"),
    ("FDX", "FDX"),
    ("Guardian", "Guardian"),
    ("WorksetManager", "WorksetManager"),
    ("ICONIC", "ICONIC"),
    ("Hypar", "Hypar"),
    ("Ideate", "Ideate"),
    ("RhinoInside", "RhinoInside"),
    ("MCNEEL", "MCNEEL"),
    ("StreamState", "StreamState"),
    ("Unifi", "Unifi"),
]

JOURNAL_FAILURE_MARKERS = ["api_error", "fail", "exception", "fatal", "loadfailure"]

# Verified Revit API (Autodesk.Revit.DB); see https://www.revitapidocs.com/
# - Schema: ListSchemas(), GUID, SchemaName, VendorId, ReadAccessGranted(), WriteAccessGranted()
# - ExtensibleStorageFilter(GuidschemaGuid): filter by schema
# - FilteredElementCollector(Document).WherePasses(ElementFilter).GetElementCount()
# - Application.RecordingJournalFilename; Document.Application


def _format_file_size(size_bytes):
    """Return human-readable size (e.g. '1.2 MB', '450 KB')."""
    if size_bytes is None or size_bytes < 0:
        return "?"
    if size_bytes < 1024:
        return "{} B".format(size_bytes)
    if size_bytes < 1024 * 1024:
        return "{:.1f} KB".format(size_bytes / 1024.0)
    return "{:.1f} MB".format(size_bytes / (1024.0 * 1024.0))


def _format_journal_date(path):
    """Return last-modified date of file as string (e.g. '2026-02-06 14:30:00') or 'N/A'."""
    if not path or not os.path.isfile(path):
        return "N/A"
    try:
        mtime = os.path.getmtime(path)
        return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return "N/A"


def get_journal_hints(doc):
    """Get current journal file path and scan FULL file for lines that hint at schema/add-in activity.
    Revit API: Application.RecordingJournalFilename. Scans entire journal line-by-line (memory-safe).
    Journal files can grow large (many MB per session); we iterate without loading all into memory.
    """
    try:
        app = doc.Application  # Document.Application property
        path = app.RecordingJournalFilename  # Application.RecordingJournalFilename property (revitapidocs)
        if not path or not isinstance(path, str) or not path.strip():
            return "Journal path not available (RecordingJournalFilename empty).", None, []
        path = path.strip()
        if not os.path.isfile(path):
            return path, None, ["(File not yet created or path not found.)"]
    except Exception as e:
        return "Journal path error: {}".format(e), None, []

    try:
        size_bytes = os.path.getsize(path)
    except Exception:
        size_bytes = None

    try:
        # Use io.open for IronPython: built-in open() does not accept encoding/errors.
        # Scan FULL file line-by-line so we don't load huge journals into memory.
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            key_lower = [k.lower() for k in JOURNAL_HINT_KEYWORDS]
            seen = set()
            unique = []
            max_hits = 150
            for line in f:
                line_lower = line.lower()
                if any(k in line_lower for k in key_lower):
                    h = line.strip()[:200]
                    if h not in seen and len(unique) < max_hits:
                        seen.add(h)
                        unique.append(h)
        return path, size_bytes, unique
    except IOError as e:
        return path, size_bytes, ["(Could not read file — in use or locked: {})".format(e)]
    except Exception as e:
        return path, size_bytes, ["(Read error: {})".format(e)]


def _schema_names_to_journal_keywords(schema_names):
    """From a list of schema names, return set of journal search keywords (add-in/product names)."""
    keywords = set()
    for name in (schema_names or []):
        for substr, kw in SCHEMA_TO_JOURNAL_KEYWORDS:
            if substr in name:
                keywords.add(kw)
    return keywords


def get_journal_failures_for_keywords(journal_path, keywords, max_lines=50):
    """Scan journal for lines that contain any of keywords AND any failure marker (API_ERROR, fail, exception, etc.).
    Returns list of line snippets (trimmed, deduplicated). Used for doc-unique schema deep dive.
    """
    if not journal_path or not os.path.isfile(journal_path) or not keywords:
        return []
    try:
        key_lower = [k.lower() for k in keywords]
        fail_lower = [m.lower() for m in JOURNAL_FAILURE_MARKERS]
        seen = set()
        result = []
        with io.open(journal_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_lower = line.lower()
                if not any(m in line_lower for m in fail_lower):
                    continue
                if not any(k in line_lower for k in key_lower):
                    continue
                h = line.strip()[:250]
                if h not in seen and len(result) < max_lines:
                    seen.add(h)
                    result.append(h)
        return result
    except Exception:
        return []


def _report_schemas_for_doc(out, doc, schemas, doc_label, only_names=None):
    """Write schema list for one document. If only_names is set, list only those schema names (compare mode)."""
    if not schemas:
        out.write("No Extensible Storage schemas in this model.", OUTPUT.Style.Subtitle)
        out.write("No schemas from you or other consultants. The model is clean.")
        return
    schema_report_lines = []
    external_count = 0
    for s in schemas:
        try:
            name = s.SchemaName if s.SchemaName else str(s.GUID)  # Schema.SchemaName, .GUID
        except Exception:
            name = "<unnamed>"
        if only_names is not None and name not in only_names:
            continue
        try:
            vendor_id = s.VendorId  # Schema.VendorId property
        except Exception:
            vendor_id = "<unknown>"
        is_external = vendor_id != ENNEAD_VENDOR_ID
        if is_external:
            external_count += 1
        try:
            can_read = s.ReadAccessGranted()   # Schema.ReadAccessGranted() method
            can_write = s.WriteAccessGranted() # Schema.WriteAccessGranted() method
        except Exception:
            can_read = can_write = False
        tag = " [OTHER CONSULTANT]" if is_external else " (yours / EnneadTab)"
        schema_report_lines.append("{} — VendorId: {} {} | ReadOK={} WriteOK={}".format(
            name, vendor_id, tag, can_read, can_write))
    n = len(schema_report_lines)
    yours_count = n - external_count
    out.write("{} ({} in this doc — yours: {}, other consultants: {})".format(
        doc_label, n, yours_count, external_count), OUTPUT.Style.Subtitle)
    out.write(schema_report_lines)


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def check_external_schema(doc):
    """List Extensible Storage schemas; if 2+ project docs are open, compare and show diff for all."""
    # Schema.ListSchemas() static method -> IList<Schema> (all schemas in memory)
    schemas = list(DB.ExtensibleStorage.Schema.ListSchemas())
    docs = REVIT_APPLICATION.get_top_revit_docs()
    compare_mode = len(docs) >= 2
    doc_list = docs if docs else [doc]
    first_doc = doc_list[0]

    # Journal from first doc (same session log for all)
    journal_path, journal_size_bytes, journal_hits = get_journal_hints(first_doc)

    out = OUTPUT.get_output()
    out.reset_output()

    if compare_mode:
        out.write("External Schema & Journal Report — Comparing {} documents".format(len(doc_list)), OUTPUT.Style.Title)
        titles_line = " | ".join("Doc {}: {}".format(i + 1, d.Title) for i, d in enumerate(doc_list))
        out.write(titles_line, OUTPUT.Style.Subtitle)
    else:
        out.write("External Schema & Journal Report", OUTPUT.Style.Title)
        out.write("Model: {}".format(first_doc.Title if first_doc and first_doc.Title else "N/A"), OUTPUT.Style.Subtitle)
    out.insert_divider()

    if compare_mode:
        # Per-doc: which schema names are in each document and element count per schema
        names_per_doc = [_schema_names_in_document(d, schemas) for d in doc_list]
        counts_per_doc = [_schema_element_counts_in_document(d, schemas) for d in doc_list]
        all_names = set()
        for names in names_per_doc:
            all_names |= names
        in_all_docs = all_names.copy()
        for names in names_per_doc:
            in_all_docs &= names
        in_all_docs = sorted(in_all_docs)

        for i, d in enumerate(doc_list):
            out.write("Doc {}: {}".format(i + 1, d.Title), OUTPUT.Style.Subtitle)
            _report_schemas_for_doc(out, d, schemas, "Schemas in this doc ({})".format(len(names_per_doc[i])), only_names=names_per_doc[i])
            out.insert_divider()

        out.write("Summary (diff across documents)", OUTPUT.Style.Subtitle)
        # Only in Doc N (unique to that doc) — with element count per schema
        for i, d in enumerate(doc_list):
            only_here = names_per_doc[i] - set().union(*(names_per_doc[j] for j in range(len(doc_list)) if j != i))
            only_here = sorted(only_here)
            out.write("Only in Doc {} ({}):".format(i + 1, d.Title), OUTPUT.Style.SubSubtitle)
            if only_here:
                counts = counts_per_doc[i]
                out.write(["{} — {} elements".format(name, counts.get(name, 0)) for name in only_here])
            else:
                out.write(["(none)"])
        # In multiple but not all (2 <= doc_count < N)
        in_some = set()
        for name in all_names:
            doc_count = sum(1 for j in range(len(doc_list)) if name in names_per_doc[j])
            if 2 <= doc_count < len(doc_list):
                in_some.add(name)
        if in_some:
            multi_line = []
            for name in sorted(in_some):
                parts = ["{} ({} elements)".format(doc_list[j].Title, counts_per_doc[j].get(name, 0))
                         for j in range(len(doc_list)) if name in names_per_doc[j]]
                multi_line.append("{}: in {}".format(name, ", ".join(parts)))
            out.write("In multiple documents (not all):", OUTPUT.Style.SubSubtitle)
            out.write(multi_line)
        out.write("In all {} documents:".format(len(doc_list)), OUTPUT.Style.SubSubtitle)
        if in_all_docs:
            all_lines = ["{} — {}".format(name, ", ".join("Doc {}: {} elements".format(j + 1, counts_per_doc[j].get(name, 0)) for j in range(len(doc_list)))) for name in in_all_docs]
            out.write(all_lines)
        else:
            out.write(["(none)"])

        # Deep dive: for each doc with doc-unique schemas, scan journal for potential failures related to those add-ins
        out.write("Journal: potential failures for doc-unique schemas", OUTPUT.Style.Subtitle)
        for i, d in enumerate(doc_list):
            only_here = names_per_doc[i] - set().union(*(names_per_doc[j] for j in range(len(doc_list)) if j != i))
            if not only_here:
                continue
            keywords = _schema_names_to_journal_keywords(only_here)
            failure_lines = get_journal_failures_for_keywords(journal_path, keywords)
            out.write("Doc {} ({}): {} unique schema(s); journal lines with failure + add-in keywords:".format(
                i + 1, d.Title, len(only_here)), OUTPUT.Style.SubSubtitle)
            if failure_lines:
                out.write(failure_lines)
            else:
                out.write(["(none — no API_ERROR/fail/exception lines mentioning those add-ins in this journal)"])
    else:
        _report_schemas_for_doc(out, first_doc, schemas, "All Schemas in This Model")

    out.insert_divider()
    out.write("Journal file (session log)", OUTPUT.Style.Subtitle)
    journal_file_uri = "file:///" + journal_path.replace("\\", "/")
    out.write(journal_file_uri)
    journal_date = _format_journal_date(journal_path)
    out.write("Path: {} | Size: {} | Modified: {} (full file scanned)".format(
        journal_path, _format_file_size(journal_size_bytes), journal_date))
    if journal_hits:
        out.write("Lines matching schema/add-in/error keywords:", OUTPUT.Style.SubSubtitle)
        out.write(journal_hits[:80])
        if len(journal_hits) > 80:
            out.write("... and {} more.".format(len(journal_hits) - 80), OUTPUT.Style.Footnote)
    else:
        out.write("No matching lines (or file empty/unreadable).")

    out.plot()


if __name__ == "__main__":
    check_external_schema(DOC)
