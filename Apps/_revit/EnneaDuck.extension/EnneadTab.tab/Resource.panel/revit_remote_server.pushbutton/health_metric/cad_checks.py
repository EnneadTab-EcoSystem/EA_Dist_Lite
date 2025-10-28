import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_cad_files(doc):
    """Check CAD files metrics - OPTIMIZED"""
    try:
        cad_data = {}
        
        # BEST PRACTICE: Single collector call for all import instances
        all_imports = DB.FilteredElementCollector(doc)\
            .OfClass(DB.ImportInstance)\
            .WhereElementIsNotElementType()\
            .ToElements()
        
        # OPTIMIZATION: Filter in single pass instead of multiple collectors
        imported_dwgs = []
        linked_dwgs = []
        
        for import_instance in all_imports:
            try:
                if import_instance.IsLinked:
                    linked_dwgs.append(import_instance)
                else:
                    imported_dwgs.append(import_instance)
            except:
                continue
        
        cad_data["imported_dwgs"] = len(imported_dwgs)
        cad_data["linked_dwgs"] = len(linked_dwgs)
        cad_data["dwg_files"] = len(all_imports)
        
        # OPTIMIZATION: More accurate CAD layer detection
        cad_layers_in_families = 0
        try:
            family_instances = DB.FilteredElementCollector(doc).OfClass(DB.FamilyInstance).ToElements()
            for fi in family_instances:
                try:
                    # Check if family has CAD import in its definition
                    if hasattr(fi, 'Symbol') and fi.Symbol:
                        family = fi.Symbol.Family
                        if family and hasattr(family, 'Name'):
                            # Heuristic: families with CAD imports often have "CAD" or "Import" in name
                            if 'CAD' in family.Name.upper() or 'IMPORT' in family.Name.upper():
                                cad_layers_in_families += 1
                                continue
                    
                    # Check parameters for CAD references
                    if hasattr(fi, 'GetParameters'):
                        for param in fi.GetParameters():
                            try:
                                if param and param.AsString():
                                    param_value = param.AsString()
                                    if 'CAD' in param_value.upper() or 'DWG' in param_value.upper() or 'DXF' in param_value.upper():
                                        cad_layers_in_families += 1
                                        break
                            except:
                                continue
                except:
                    continue
        except:
            pass
        
        cad_data["cad_layers_imports_in_families"] = cad_layers_in_families
        
        return cad_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

