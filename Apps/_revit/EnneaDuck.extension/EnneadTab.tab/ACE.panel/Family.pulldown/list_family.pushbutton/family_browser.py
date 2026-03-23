"""Generates an interactive HTML family browser dashboard.

Extracts family metadata from Revit and creates a self-contained HTML file
that auto-opens in the default browser. Designed to run alongside the
ListFamily deployment so users can search, filter, and compare families
while Revit places them into views.

IronPython 2.7 compatible - no f-strings, no type hints, no pathlib.
"""

import os
import io
import json
import math
import time
import webbrowser
import traceback

import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab import FOLDER, NOTIFICATION, ERROR_HANDLE
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FAMILY
from Autodesk.Revit import DB # pyright: ignore


def extract_family_data(families):
    """Extract metadata from a list of Revit families into a JSON-serializable dict.

    Args:
        families: list of DB.Family objects selected by the user

    Returns:
        list of dicts, each representing one family
    """
    doc = REVIT_APPLICATION.get_doc()
    data = []
    skip_nested = len(families) > 20

    for family in families:
        try:
            family_data = _extract_single_family(doc, family, skip_nested)
            if family_data:
                data.append(family_data)
        except Exception as e:
            print("Failed to extract data for family {}: {}".format(
                family.Name, traceback.format_exc()))

    return data


def _extract_single_family(doc, family, skip_nested=False):
    """Extract data from one Revit family.

    Args:
        doc: Revit document
        family: DB.Family object

    Returns:
        dict with family metadata
    """
    category_name = "Unknown"
    if family.FamilyCategory:
        category_name = family.FamilyCategory.Name

    is_shared = REVIT_FAMILY.is_family_shared(family.Name)
    placement_type = str(family.FamilyPlacementType)
    is_curtain_panel = family.IsCurtainPanelFamily

    # Extract types and their parameters
    type_ids = family.GetFamilySymbolIds()
    types_data = []
    all_param_names = set()

    for type_id in type_ids:
        family_type = doc.GetElement(type_id)
        if not family_type:
            continue

        type_name = family_type.LookupParameter("Type Name")
        type_name = type_name.AsString() if type_name else "Unnamed"

        # Collect type parameters
        params = {}
        for param in family_type.Parameters:
            if param.IsReadOnly:
                continue
            if param.Definition.Name in ("Type Image", "Type Comments", "URL",
                                          "Description", "Assembly Description",
                                          "Keynote", "Model", "Manufacturer",
                                          "Assembly Code", "Cost", "OmniClass Number",
                                          "OmniClass Title", "Code Name"):
                continue

            val = _get_param_value(param)
            if val is not None and val != "":
                params[param.Definition.Name] = val
                all_param_names.add(param.Definition.Name)

        types_data.append({
            "name": type_name,
            "params": params
        })

    # Extract nested family names (subfamilies used inside this family)
    nested_families = [] if skip_nested else _get_nested_families(doc, family)

    return {
        "name": family.Name,
        "category": category_name,
        "typeCount": len(types_data),
        "types": types_data,
        "paramNames": sorted(list(all_param_names)),
        "isShared": is_shared,
        "placementType": placement_type,
        "isCurtainPanel": is_curtain_panel,
        "nestedFamilies": nested_families,
        "id": family.Id.IntegerValue
    }


def _get_param_value(param):
    """Get parameter value as a display string.

    Args:
        param: DB.Parameter

    Returns:
        str or None
    """
    if not param.HasValue:
        return None

    storage = param.StorageType
    if storage == DB.StorageType.String:
        return param.AsString()
    elif storage == DB.StorageType.Integer:
        return param.AsInteger()
    elif storage == DB.StorageType.Double:
        # Convert internal units to display units
        raw = param.AsDouble()
        if math.isnan(raw) or math.isinf(raw):
            return None
        if abs(raw) < 0.0001:
            return None
        val_str = param.AsValueString()
        if val_str:
            return val_str
        return round(raw, 4)
    elif storage == DB.StorageType.ElementId:
        val_str = param.AsValueString()
        return val_str if val_str else None
    return None


def _get_nested_families(doc, family):
    """Get names of families nested inside this family.

    Opens the family document temporarily to inspect subfamilies.
    Falls back to empty list if the family doc cannot be opened.

    Args:
        doc: Revit document
        family: DB.Family object

    Returns:
        list of str (nested family names)
    """
    nested = []
    family_doc = None
    try:
        if not family.IsEditable:
            return nested
        family_doc = doc.EditFamily(family)
        if not family_doc:
            return nested
        collector = DB.FilteredElementCollector(family_doc).OfClass(DB.Family)
        for nested_fam in collector:
            nested.append(nested_fam.Name)
    except:
        pass
    finally:
        if family_doc:
            try:
                family_doc.Close(False)
            except:
                pass

    return nested


def generate_html(families_data, doc_title):
    """Generate the HTML dashboard and return the file path.

    Args:
        families_data: list of family dicts from extract_family_data()
        doc_title: Revit document title for the report header

    Returns:
        str: path to generated HTML file
    """
    html_path = FOLDER.get_local_dump_folder_file("EnneadTab_FamilyBrowser.html")

    # Group by category for summary
    categories = {}
    for fam in families_data:
        cat = fam["category"]
        if cat not in categories:
            categories[cat] = 0
        categories[cat] += 1

    total_types = sum(f["typeCount"] for f in families_data)

    # Serialize data for JavaScript
    json_data = json.dumps(families_data)
    json_data = json_data.replace('</', '<\\/')

    timestamp = time.strftime("%Y-%m-%d %H:%M")

    html = _build_html(json_data, doc_title, timestamp,
                       len(families_data), total_types, len(categories))

    with io.open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    return html_path


def open_browser(html_path):
    """Open the HTML file in the default browser.

    Args:
        html_path: str path to HTML file
    """
    try:
        webbrowser.open("file:///{}".format(html_path.replace("\\", "/")))
    except:
        try:
            os.startfile(html_path)
        except:
            print("Could not auto-open browser. File saved at: {}".format(html_path))


@ERROR_HANDLE.try_catch_error()
def launch_family_browser(families):
    """Main entry point: extract data, generate HTML, open browser.

    Args:
        families: list of DB.Family objects

    Returns:
        str: path to generated HTML file, or None on failure
    """
    if not families:
        return None

    doc = REVIT_APPLICATION.get_doc()
    doc_title = doc.Title if doc.Title else "Untitled"

    NOTIFICATION.messenger("Generating family browser...")

    families_data = extract_family_data(families)
    if not families_data:
        NOTIFICATION.messenger("No family data extracted.")
        return None

    html_path = generate_html(families_data, doc_title)
    open_browser(html_path)

    return html_path


def _html_escape(s):
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _build_html(json_data, doc_title, timestamp, family_count, type_count, category_count):
    """Build the complete HTML string for the family browser.

    Returns:
        str: Full HTML document
    """
    # NOTE: Using string concatenation for IronPython 2.7 compatibility.
    # CSS uses `border-inline-start` instead of `border-left` per CLAUDE.md.

    safe_title = _html_escape(doc_title)
    safe_timestamp = _html_escape(timestamp)

    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Family Browser - """ + safe_title + """</title>
<style>
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #1e2a45;
    --bg-hover: #253553;
    --accent: #e07a3a;
    --accent-light: #f4a261;
    --text-primary: #e8e8e8;
    --text-secondary: #a0a8b8;
    --text-muted: #6b7280;
    --border: #2a3a5c;
    --shared-badge: #4ade80;
    --curtain-badge: #818cf8;
    --tag-bg: #1e3a5f;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    min-height: 100vh;
}
.header {
    background: linear-gradient(135deg, var(--bg-secondary), #1a1a3e);
    padding: 24px 32px;
    box-shadow: inset 0 -2px 0 0 var(--border);
}
.header h1 {
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 4px;
}
.header .subtitle {
    color: var(--text-secondary);
    font-size: 13px;
}
.stats-bar {
    display: flex;
    gap: 24px;
    padding: 16px 32px;
    background: var(--bg-secondary);
    box-shadow: inset 0 -1px 0 0 var(--border);
}
.stat-item {
    display: flex;
    align-items: center;
    gap: 8px;
}
.stat-num {
    font-size: 24px;
    font-weight: 700;
    color: var(--accent);
}
.stat-label {
    font-size: 12px;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.toolbar {
    display: flex;
    gap: 12px;
    padding: 16px 32px;
    align-items: center;
    flex-wrap: wrap;
    background: var(--bg-primary);
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: inset 0 -1px 0 0 var(--border);
}
.search-box {
    flex: 1;
    min-width: 250px;
    padding: 10px 16px;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-primary);
    font-size: 14px;
    outline: none;
    transition: border-color 0.2s;
}
.search-box:focus {
    border-color: var(--accent);
}
.search-box::placeholder {
    color: var(--text-muted);
}
.filter-btn {
    padding: 8px 16px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    font-size: 13px;
    cursor: pointer;
    transition: all 0.2s;
    white-space: nowrap;
}
.filter-btn:hover, .filter-btn.active {
    background: var(--accent);
    color: #fff;
    border-color: var(--accent);
}
.view-toggle {
    display: flex;
    gap: 4px;
    margin-inline-start: auto;
}
.view-toggle button {
    padding: 8px 12px;
    border-radius: 6px;
    border: 1px solid var(--border);
    background: var(--bg-secondary);
    color: var(--text-secondary);
    cursor: pointer;
    font-size: 13px;
}
.view-toggle button.active {
    background: var(--bg-card);
    color: var(--text-primary);
    border-color: var(--accent);
}
.main-content {
    display: flex;
    min-height: calc(100vh - 200px);
}
.sidebar {
    width: 240px;
    min-width: 240px;
    padding: 16px;
    background: var(--bg-secondary);
    box-shadow: inset -1px 0 0 0 var(--border);
    overflow-y: auto;
    max-height: calc(100vh - 200px);
    position: sticky;
    top: 60px;
}
.sidebar h3 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-muted);
    margin-bottom: 12px;
}
.cat-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    color: var(--text-secondary);
    transition: all 0.15s;
    margin-bottom: 2px;
}
.cat-item:hover, .cat-item.active {
    background: var(--bg-hover);
    color: var(--text-primary);
}
.cat-item.active {
    box-shadow: inset 3px 0 0 0 var(--accent);
}
.cat-count {
    background: var(--bg-primary);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    color: var(--text-muted);
}
.content-area {
    flex: 1;
    padding: 24px 32px;
    overflow-y: auto;
}
.category-section {
    margin-bottom: 32px;
}
.category-header {
    font-size: 16px;
    font-weight: 600;
    color: var(--accent-light);
    margin-bottom: 16px;
    padding-bottom: 8px;
    box-shadow: inset 0 -1px 0 0 var(--border);
}
/* Card grid view */
.family-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: 16px;
}
.family-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 20px;
    cursor: pointer;
    transition: all 0.2s;
}
.family-card:hover {
    border-color: var(--accent);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0,0,0,0.3);
}
.family-card.expanded {
    grid-column: 1 / -1;
}
.card-top {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    margin-bottom: 12px;
}
.family-name {
    font-size: 15px;
    font-weight: 600;
    word-break: break-word;
}
.type-badge {
    background: var(--tag-bg);
    color: var(--accent-light);
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 12px;
    white-space: nowrap;
    margin-inline-start: 8px;
    flex-shrink: 0;
}
.card-meta {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 12px;
}
.badge {
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 11px;
    font-weight: 500;
}
.badge-shared {
    background: rgba(74, 222, 128, 0.15);
    color: var(--shared-badge);
}
.badge-curtain {
    background: rgba(129, 140, 248, 0.15);
    color: var(--curtain-badge);
}
.badge-placement {
    background: rgba(224, 122, 58, 0.1);
    color: var(--accent-light);
}
.badge-nested {
    background: rgba(96, 165, 250, 0.15);
    color: #60a5fa;
}
.card-types {
    font-size: 12px;
    color: var(--text-muted);
    margin-bottom: 8px;
}
.type-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.type-chip {
    background: var(--bg-primary);
    padding: 3px 10px;
    border-radius: 4px;
    font-size: 12px;
    color: var(--text-secondary);
}
.type-chip-more {
    color: var(--accent);
    cursor: pointer;
}

/* Table view */
.family-table {
    width: 100%;
    border-collapse: collapse;
}
.family-table th {
    text-align: start;
    padding: 10px 16px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    background: var(--bg-secondary);
    position: sticky;
    top: 60px;
    z-index: 10;
}
.family-table td {
    padding: 12px 16px;
    font-size: 13px;
    box-shadow: inset 0 -1px 0 0 var(--border);
}
.family-table tr:hover td {
    background: var(--bg-hover);
}
.family-table tr {
    cursor: pointer;
}

/* Detail panel (expanded card) */
.detail-panel {
    margin-top: 16px;
    padding-top: 16px;
    box-shadow: inset 0 1px 0 0 var(--border);
}
.detail-section {
    margin-bottom: 16px;
}
.detail-section h4 {
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: var(--text-muted);
    margin-bottom: 8px;
}
.param-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}
.param-table th {
    text-align: start;
    padding: 6px 10px;
    background: var(--bg-primary);
    color: var(--text-muted);
    font-size: 11px;
    text-transform: uppercase;
}
.param-table td {
    padding: 6px 10px;
    box-shadow: inset 0 -1px 0 0 rgba(42,58,92,0.5);
    color: var(--text-secondary);
}
.param-table tr:hover td {
    background: rgba(42,58,92,0.3);
}
.nested-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}
.nested-chip {
    background: rgba(96, 165, 250, 0.1);
    color: #60a5fa;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
}
.empty-state {
    text-align: center;
    padding: 60px 20px;
    color: var(--text-muted);
}
.empty-state span {
    font-size: 48px;
    display: block;
    margin-bottom: 16px;
}
.highlight {
    background: rgba(224, 122, 58, 0.3);
    border-radius: 2px;
    padding: 0 2px;
}
.footer {
    text-align: center;
    padding: 16px;
    color: var(--text-muted);
    font-size: 11px;
}
@media (max-width: 768px) {
    .sidebar { display: none; }
    .family-grid { grid-template-columns: 1fr; }
    .toolbar { padding: 12px 16px; }
    .content-area { padding: 16px; }
}
</style>
</head>
<body>

<div class="header">
    <h1>Family Browser</h1>
    <div class="subtitle">""" + safe_title + """ -- Generated """ + safe_timestamp + """</div>
</div>

<div class="stats-bar">
    <div class="stat-item">
        <div class="stat-num" id="family-count">""" + str(family_count) + """</div>
        <div class="stat-label">Families</div>
    </div>
    <div class="stat-item">
        <div class="stat-num" id="type-count">""" + str(type_count) + """</div>
        <div class="stat-label">Types</div>
    </div>
    <div class="stat-item">
        <div class="stat-num" id="cat-count">""" + str(category_count) + """</div>
        <div class="stat-label">Categories</div>
    </div>
</div>

<div class="toolbar">
    <input type="text" class="search-box" id="search"
           placeholder="Search families by name, category, parameter..."
           autocomplete="off">
    <button class="filter-btn" data-filter="shared" onclick="toggleFilter('shared')">Shared</button>
    <button class="filter-btn" data-filter="curtain" onclick="toggleFilter('curtain')">Curtain Panel</button>
    <button class="filter-btn" data-filter="nested" onclick="toggleFilter('nested')">Has Nested</button>
    <div class="view-toggle">
        <button id="btn-grid" class="active" onclick="setView('grid')">Grid</button>
        <button id="btn-table" onclick="setView('table')">Table</button>
    </div>
</div>

<div class="main-content">
    <div class="sidebar" id="sidebar">
        <h3>Categories</h3>
        <div class="cat-item active" data-cat="all" onclick="filterCategory('all')">
            <span>All Families</span>
            <span class="cat-count" id="sidebar-total">""" + str(family_count) + """</span>
        </div>
        <div id="cat-list"></div>
    </div>

    <div class="content-area" id="content-area">
        <!-- Rendered by JS -->
    </div>
</div>

<div class="footer">EnneadTab Family Browser</div>

<script>
var ALL_DATA = """ + json_data + """;

var currentView = 'grid';
var currentCategory = 'all';
var activeFilters = {};
var expandedCard = null;
var searchTerm = '';

function init() {
    buildSidebar();
    render();
    document.getElementById('search').addEventListener('input', function(e) {
        searchTerm = e.target.value.toLowerCase();
        render();
    });
}

function buildSidebar() {
    var cats = {};
    for (var i = 0; i < ALL_DATA.length; i++) {
        var c = ALL_DATA[i].category;
        cats[c] = (cats[c] || 0) + 1;
    }
    var sorted = Object.keys(cats).sort();
    var html = '';
    for (var j = 0; j < sorted.length; j++) {
        var cat = sorted[j];
        html += '<div class="cat-item" data-cat="' + esc(cat) + '">' +
                '<span>' + esc(cat) + '</span>' +
                '<span class="cat-count">' + cats[cat] + '</span></div>';
    }
    var catList = document.getElementById('cat-list');
    catList.innerHTML = html;
    catList.addEventListener('click', function(e) {
        var item = e.target.closest('.cat-item');
        if (!item) return;
        var cat = item.getAttribute('data-cat');
        if (cat) filterCategory(cat);
    });
}

function filterCategory(cat) {
    currentCategory = cat;
    expandedCard = null;
    // Update sidebar active state
    var items = document.querySelectorAll('.cat-item');
    for (var i = 0; i < items.length; i++) {
        items[i].classList.toggle('active', items[i].getAttribute('data-cat') === cat);
    }
    render();
}

function toggleFilter(key) {
    activeFilters[key] = !activeFilters[key];
    var btns = document.querySelectorAll('.filter-btn[data-filter="' + key + '"]');
    for (var i = 0; i < btns.length; i++) {
        btns[i].classList.toggle('active', activeFilters[key]);
    }
    render();
}

function setView(view) {
    currentView = view;
    document.getElementById('btn-grid').classList.toggle('active', view === 'grid');
    document.getElementById('btn-table').classList.toggle('active', view === 'table');
    expandedCard = null;
    render();
}

function getFiltered() {
    var result = [];
    for (var i = 0; i < ALL_DATA.length; i++) {
        var f = ALL_DATA[i];
        if (currentCategory !== 'all' && f.category !== currentCategory) continue;
        if (activeFilters.shared && !f.isShared) continue;
        if (activeFilters.curtain && !f.isCurtainPanel) continue;
        if (activeFilters.nested && f.nestedFamilies.length === 0) continue;
        if (searchTerm) {
            var haystack = (f.name + ' ' + f.category + ' ' + f.placementType).toLowerCase();
            // Also search in type names and param values
            for (var t = 0; t < f.types.length; t++) {
                haystack += ' ' + f.types[t].name.toLowerCase();
                var pk = Object.keys(f.types[t].params);
                for (var p = 0; p < pk.length; p++) {
                    haystack += ' ' + pk[p].toLowerCase() + ' ' + String(f.types[t].params[pk[p]]).toLowerCase();
                }
            }
            for (var n = 0; n < f.nestedFamilies.length; n++) {
                haystack += ' ' + f.nestedFamilies[n].toLowerCase();
            }
            if (haystack.indexOf(searchTerm) === -1) continue;
        }
        result.push(f);
    }
    return result;
}

function render() {
    var filtered = getFiltered();
    updateStats(filtered);

    if (filtered.length === 0) {
        document.getElementById('content-area').innerHTML =
            '<div class="empty-state"><span>&#8709;</span>No families match your filters.</div>';
        return;
    }

    if (currentView === 'grid') {
        renderGrid(filtered);
    } else {
        renderTable(filtered);
    }
}

function updateStats(filtered) {
    document.getElementById('family-count').textContent = filtered.length;
    var tc = 0;
    var cats = {};
    for (var i = 0; i < filtered.length; i++) {
        tc += filtered[i].typeCount;
        cats[filtered[i].category] = true;
    }
    document.getElementById('type-count').textContent = tc;
    document.getElementById('cat-count').textContent = Object.keys(cats).length;
}

function renderGrid(data) {
    // Group by category
    var groups = {};
    var order = [];
    for (var i = 0; i < data.length; i++) {
        var c = data[i].category;
        if (!groups[c]) { groups[c] = []; order.push(c); }
        groups[c].push(data[i]);
    }

    var html = '';
    for (var g = 0; g < order.length; g++) {
        var cat = order[g];
        var families = groups[cat];
        html += '<div class="category-section"><div class="category-header">' +
                esc(cat) + ' (' + families.length + ')</div><div class="family-grid">';

        for (var f = 0; f < families.length; f++) {
            html += buildCard(families[f]);
        }
        html += '</div></div>';
    }
    document.getElementById('content-area').innerHTML = html;
}

function buildCard(fam) {
    var isExpanded = expandedCard === fam.id;
    var cls = 'family-card' + (isExpanded ? ' expanded' : '');

    var html = '<div class="' + cls + '" onclick="toggleExpand(' + fam.id + ')">';
    html += '<div class="card-top"><span class="family-name">' + highlightText(fam.name) + '</span>';
    html += '<span class="type-badge">' + fam.typeCount + ' type' + (fam.typeCount !== 1 ? 's' : '') + '</span></div>';

    // Badges
    html += '<div class="card-meta">';
    if (fam.isShared) html += '<span class="badge badge-shared">Shared</span>';
    if (fam.isCurtainPanel) html += '<span class="badge badge-curtain">Curtain Panel</span>';
    html += '<span class="badge badge-placement">' + esc(fam.placementType) + '</span>';
    if (fam.nestedFamilies.length > 0) html += '<span class="badge badge-nested">' + fam.nestedFamilies.length + ' nested</span>';
    html += '</div>';

    // Type chips (show first 5)
    var maxShow = 5;
    html += '<div class="type-list">';
    for (var t = 0; t < Math.min(fam.types.length, maxShow); t++) {
        html += '<span class="type-chip">' + highlightText(fam.types[t].name) + '</span>';
    }
    if (fam.types.length > maxShow) {
        html += '<span class="type-chip type-chip-more">+' + (fam.types.length - maxShow) + ' more</span>';
    }
    html += '</div>';

    // Expanded detail panel
    if (isExpanded) {
        html += buildDetailPanel(fam);
    }

    html += '</div>';
    return html;
}

function buildDetailPanel(fam) {
    var html = '<div class="detail-panel" onclick="event.stopPropagation()">';

    // Parameter comparison table
    if (fam.paramNames.length > 0 && fam.types.length > 0) {
        html += '<div class="detail-section"><h4>Parameter Values</h4>';
        html += '<div style="overflow-x:auto"><table class="param-table"><thead><tr><th>Parameter</th>';
        for (var t = 0; t < fam.types.length; t++) {
            html += '<th>' + esc(fam.types[t].name) + '</th>';
        }
        html += '</tr></thead><tbody>';

        for (var p = 0; p < fam.paramNames.length; p++) {
            var pname = fam.paramNames[p];
            html += '<tr><td style="font-weight:500;color:var(--text-primary)">' + esc(pname) + '</td>';
            for (var t2 = 0; t2 < fam.types.length; t2++) {
                var val = fam.types[t2].params[pname];
                html += '<td>' + (val !== undefined ? esc(String(val)) : '--') + '</td>';
            }
            html += '</tr>';
        }
        html += '</tbody></table></div></div>';
    }

    // Nested families
    if (fam.nestedFamilies.length > 0) {
        html += '<div class="detail-section"><h4>Nested Families</h4><div class="nested-list">';
        for (var n = 0; n < fam.nestedFamilies.length; n++) {
            html += '<span class="nested-chip">' + esc(fam.nestedFamilies[n]) + '</span>';
        }
        html += '</div></div>';
    }

    html += '</div>';
    return html;
}

function renderTable(data) {
    var html = '<table class="family-table"><thead><tr>' +
               '<th>Family Name</th><th>Category</th><th>Types</th>' +
               '<th>Placement</th><th>Shared</th><th>Nested</th></tr></thead><tbody>';

    for (var i = 0; i < data.length; i++) {
        var f = data[i];
        html += '<tr onclick="setView(\\'grid\\'); expandedCard=' + f.id + '; render();">';
        html += '<td style="font-weight:500">' + highlightText(f.name) + '</td>';
        html += '<td>' + esc(f.category) + '</td>';
        html += '<td><span class="type-badge">' + f.typeCount + '</span></td>';
        html += '<td><span class="badge badge-placement">' + esc(f.placementType) + '</span></td>';
        html += '<td>' + (f.isShared ? '<span class="badge badge-shared">Yes</span>' : '--') + '</td>';
        html += '<td>' + (f.nestedFamilies.length > 0 ? '<span class="badge badge-nested">' + f.nestedFamilies.length + '</span>' : '--') + '</td>';
        html += '</tr>';
    }
    html += '</tbody></table>';
    document.getElementById('content-area').innerHTML = html;
}

function toggleExpand(id) {
    expandedCard = (expandedCard === id) ? null : id;
    render();
}

function highlightText(rawText) {
    if (!searchTerm) return esc(rawText);
    var lower = rawText.toLowerCase();
    var idx = lower.indexOf(searchTerm);
    if (idx === -1) return esc(rawText);
    return esc(rawText.substring(0, idx)) +
           '<span class="highlight">' + esc(rawText.substring(idx, idx + searchTerm.length)) + '</span>' +
           esc(rawText.substring(idx + searchTerm.length));
}

function esc(s) {
    if (s === null || s === undefined) return '';
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}

init();
</script>
</body>
</html>"""
