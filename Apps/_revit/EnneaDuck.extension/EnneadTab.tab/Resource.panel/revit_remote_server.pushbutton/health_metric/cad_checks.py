import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_cad_files(doc):
    """Check CAD files metrics"""
    try:
        cad_data = {}
        
        # DWG files
        all_dwgs = DB.FilteredElementCollector(doc).OfClass(DB.ImportInstance).WhereElementIsNotElementType().ToElements()
        
        # Imported DWGs (not linked)
        imported_dwgs = [x for x in all_dwgs if not x.IsLinked]
        cad_data["imported_dwgs"] = len(imported_dwgs)
        
        # Linked DWGs
        linked_dwgs = [x for x in all_dwgs if x.IsLinked]
        cad_data["linked_dwgs"] = len(linked_dwgs)
        
        # Total DWG files
        cad_data["dwg_files"] = len(all_dwgs)
        
        # CAD layers in families
        cad_layers_in_families = 0
        try:
            family_instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).ToElements()
            for fi in family_instances:
                if hasattr(fi, 'GetParameters'):
                    for param in fi.GetParameters():
                        if param and param.AsString() and 'CAD' in param.AsString():
                            cad_layers_in_families += 1
        except:
            pass
        cad_data["cad_layers_imports_in_families"] = cad_layers_in_families
        
        return cad_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

