# Feature: Model Exporter for Remote Revit Server

## 🌿 Git Branch Strategy
**Branch Name:** `feature/model-exporter`

```bash
# Create and checkout feature branch from main
git checkout main
git pull origin main
git checkout -b feature/model-exporter

# Work on model exporter...
git add .
git commit -m "feat: Add model exporter infrastructure"

# When complete and tested:
git push origin feature/model-exporter
# Create PR to merge into main
```

**⚠️ DO NOT work on main branch directly!**

---

## Overview
Add a standalone model exporter that can export views/sheets to images (JPG), PDFs, and DWGs without relying on EnneadTab modules. This exporter should work alongside the health metric extractor and handle failures gracefully.

## Requirements Summary
- Export formats: **Image (JPG), PDF, DWG**
- Target views/sheets: **First 10 items from print-set** (fallback to first 10 sheets if no print-set)
- Must be **standalone** (no EnneadTab dependencies)
- **Error resilient**: Failures should not stop health metric extraction
- Output errors/tracebacks in JSON for later analysis

## Proposed Architecture

### File Structure
```
health_metric/
├── __init__.py (existing health metric)
model_exporter/
├── __init__.py (main ModelExporter class)
├── image_exporter.py (JPG export logic)
├── pdf_exporter.py (PDF export logic)
├── dwg_exporter.py (DWG export logic)
└── export_helpers.py (shared utilities: view selection, path management)
```

### Output Structure
```
task_output/
└── [project_folder]/
    └── [model_name]_export_folder/
        ├── images/
        │   ├── Sheet_001.jpg
        │   └── Sheet_002.jpg
        ├── pdfs/
        │   ├── Sheet_001.pdf
        │   └── Sheet_002.pdf
        └── dwgs/
            ├── Sheet_001.dwg
            └── Sheet_002.dwg
```

## Implementation Plan

### Phase 1: Core Infrastructure
**File:** `model_exporter/__init__.py`

```python
class ModelExporter:
    def __init__(self, doc, output_base_path):
        self.doc = doc
        self.output_base_path = output_base_path
        self.report = {
            "export_status": "not_started",
            "errors": [],
            "exported_files": {
                "images": [],
                "pdfs": [],
                "dwgs": []
            }
        }
    
    def export_all(self):
        """Main export orchestrator - catches all errors"""
        try:
            views_to_export = self._get_views_to_export()
            self._export_images(views_to_export)
            self._export_pdfs(views_to_export)
            self._export_dwgs(views_to_export)
            self.report["export_status"] = "completed"
        except Exception as e:
            self.report["export_status"] = "failed"
            self.report["errors"].append({
                "stage": "export_all",
                "error": str(e),
                "traceback": traceback.format_exc()
            })
        return self.report
```

### Phase 2: View Selection Logic
**File:** `model_exporter/export_helpers.py`

Key function: `get_views_to_export(doc)`
- Check for print sets (ViewSheetSet)
- Get first 10 items from print set
- Fallback: Get first 10 sheets from document
- Filter out template sheets

**Questions for User:**
1. **Print Set Selection**: If there are multiple print sets, should we use a specific one (e.g., by name pattern) or just the first one found?
2. **View vs Sheet**: Should we export both sheets AND views, or only sheets? (Current understanding: sheets only)
3. **Template Sheets**: Should we skip sheets marked as templates or with specific naming patterns (e.g., starting with underscore)?

### Phase 3: Image Export
**File:** `model_exporter/image_exporter.py`

Uses Revit API:
```python
# Key API: ImageExportOptions
options = DB.ImageExportOptions()
options.FilePath = output_path
options.ZoomType = DB.ZoomFitType.FitToPage
options.PixelSize = 1920  # Width in pixels
options.ImageResolution = DB.ImageResolution.DPI_150
options.FitDirection = DB.FitDirectionType.Horizontal
options.ExportRange = DB.ExportRange.SetOfViews
options.SetViewsAndSheets([view_ids])

doc.ExportImage(options)
```

**Questions for User:**
1. **Image Resolution**: What resolution should we use? (DPI_72, DPI_150, DPI_300, DPI_600)?
2. **Image Size**: What pixel dimensions? (1920x1080? 2560x1440? Or fit to sheet size?)
3. **File Naming**: Should we use sheet number + name, or just sheet number? Format: `[number]_[name].jpg` or `[number].jpg`?
4. **Color Mode**: RGB or Grayscale? (Consider file size vs quality)

### Phase 4: PDF Export
**File:** `model_exporter/pdf_exporter.py`

Uses Revit API:
```python
# Key API: PDFExportOptions
options = DB.PDFExportOptions()
options.FileName = pdf_filename  # Without extension
options.Combine = False  # Individual PDFs per sheet
# OR
options.Combine = True   # Single multi-page PDF

view_ids = List[DB.ElementId]([view.Id for view in views])
doc.Export(output_folder, view_ids, options)
```

**Questions for User:**
1. **Combine PDFs**: Should we export as individual PDF files per sheet, or combine into one multi-page PDF?
2. **PDF Quality**: Should we use print settings, or custom raster quality? (HiddenLineProcessing, RayTracing, etc.)?
3. **Include Hidden Info**: Should we include hidden lines, hidden categories, or export exactly as displayed?
4. **File Naming**: Same as images - what naming convention?

### Phase 5: DWG Export
**File:** `model_exporter/dwg_exporter.py`

Uses Revit API:
```python
# Key API: DWGExportOptions
options = DB.DWGExportOptions()
options.MergedViews = False  # Export each view separately
options.FileVersion = DB.ACADVersion.R2018  # DWG version
options.LayerSettings = DB.ExportLayerOptions.AIA  # Layer naming standard
options.LineScaling = DB.LineScaling.PaperSpace
options.PropOverrides = DB.PropOverrideMode.ByEntity
options.SharedCoords = False  # Use internal coordinates

view_ids = List[DB.ElementId]([view.Id for view in views])
doc.Export(output_folder, "", view_ids, options)
```

**Questions for User:**
1. **DWG Version**: What AutoCAD version should we target? (R2018, R2013, R2010, R2007)?
2. **Layer Standard**: AIA layer naming or custom? (AIA, ISO13567, BS1192, Custom)?
3. **Coordinate System**: Should we use shared coordinates or internal/project coordinates?
4. **Export Solid Fills**: Should we preserve solid filled regions as hatches or export differently?
5. **Text Handling**: Export text as text entities or explode to lines?
6. **Line Weights**: Export with line weights or normalize?

### Phase 6: Integration & Error Handling

**Integration Point:** `revit_remote_server_script.py`
```python
# After health metric extraction
health_report = health_metric.check()

# Add model exporter
try:
    from model_exporter import ModelExporter
    exporter = ModelExporter(doc, output_base_path)
    export_report = exporter.export_all()
    
    # Merge reports
    final_report = health_report.copy()
    final_report["model_export"] = export_report
except Exception as e:
    # Don't fail - add error to report
    final_report["model_export"] = {
        "export_status": "initialization_failed",
        "error": str(e),
        "traceback": traceback.format_exc()
    }
```

**Error Handling Strategy:**
- Each export method (image/pdf/dwg) wrapped in try/except
- Collect errors but continue with other formats
- Include full traceback in JSON report
- Never propagate exceptions to health metric

## Testing Plan

### Test Cases
1. **Happy Path**: Project with print set, exports all 3 formats successfully
2. **No Print Set**: Project without print set, falls back to first 10 sheets
3. **Partial Failure**: One export type fails, others succeed
4. **No Sheets**: Project with no sheets, handles gracefully
5. **Permission Issues**: Output folder is read-only
6. **Large Files**: Performance with large complex sheets

### Manual Testing Checklist
- [ ] Export images from print set
- [ ] Export PDFs from print set
- [ ] Export DWGs from print set
- [ ] Fallback to first 10 sheets when no print set exists
- [ ] Verify output folder structure matches specification
- [ ] Verify errors are captured in JSON report
- [ ] Confirm health metric continues after export failure
- [ ] Test with workshared project
- [ ] Test with non-workshared project
- [ ] Validate file naming consistency

## Implementation Notes

### API Reference Sources
Study these EnneadTab modules for export patterns (WITHOUT importing them):
- `Apps/lib/EnneadTab/REVIT/REVIT_EXPORT.py` - Export utilities
- `Apps/_revit/EnneaDuck.extension/EnneadTab.tab/Export.panel/*` - Export buttons

### Key Revit API Classes to Use
- `DB.ImageExportOptions` - Image export
- `DB.PDFExportOptions` - PDF export  
- `DB.DWGExportOptions` - DWG export
- `DB.ViewSheetSet` - Print sets
- `DB.ViewSheet` - Sheet elements
- `DB.FilteredElementCollector` - Finding sheets/print sets

### Performance Considerations
- Export operations can be slow (1-10 seconds per sheet)
- Add progress logging: `print("STATUS: Exporting sheet 3/10...")`
- Consider timeout limits (max 5 minutes total?)
- Batch exports where possible (API supports multiple sheets)

## Open Questions & Decisions Needed

### Critical Decisions (Block Implementation)
1. **Image Resolution & Size** - Impacts file size and quality
2. **PDF Combine Strategy** - Single file vs multiple files
3. **DWG Version & Standards** - Must match user's workflow
4. **Print Set Selection** - Which one if multiple exist?

### Nice-to-Have Decisions
5. **Naming Conventions** - User preference for file names
6. **Progress Reporting** - How detailed should status messages be?
7. **Timeout Limits** - Should we abort after X minutes?
8. **Retry Logic** - Should we retry failed exports?

### Implementation Preferences
9. **Module Organization** - Keep separate files or combine some?
10. **Configuration** - Hard-code settings or add config file?
11. **Logging Level** - How verbose should error messages be?

## Timeline Estimate
- **Phase 1-2** (Infrastructure + View Selection): 2-3 hours
- **Phase 3** (Image Export): 1-2 hours
- **Phase 4** (PDF Export): 1-2 hours
- **Phase 5** (DWG Export): 2-3 hours (most complex)
- **Phase 6** (Integration): 1 hour
- **Testing & Debug**: 2-4 hours
- **Total**: 9-15 hours

## Next Steps
1. ✅ User reviews this plan
2. ⏸️ User answers critical questions (1-4)
3. ⏸️ **Create feature branch**: `feature/model-exporter`
4. ⏸️ Implement Phase 1-2 (core + view selection)
5. ⏸️ Implement Phase 3-5 (exporters)
6. ⏸️ Implement Phase 6 (integration)
7. ⏸️ Test and iterate
8. ⏸️ Push to feature branch and create PR
9. ⏸️ Review, approve, and merge to main

