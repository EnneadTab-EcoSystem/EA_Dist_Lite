import traceback
from Autodesk.Revit import DB # pyright: ignore


def check_file_size(doc):
    """Check file size in MB"""
    try:
        file_size_data = {}
        
        # Get file path
        file_path = doc.PathName
        if file_path:
            try:
                import os
                file_size_bytes = os.path.getsize(file_path)
                file_size_mb = file_size_bytes / (1024.0 * 1024.0)
                file_size_data["file_size_mb"] = round(file_size_mb, 2)
                file_size_data["file_size_bytes"] = file_size_bytes
                file_size_data["file_path"] = file_path
            except:
                file_size_data["file_size_mb"] = 0
                file_size_data["file_size_bytes"] = 0
                file_size_data["error"] = "Could not determine file size"
        else:
            file_size_data["file_size_mb"] = 0
            file_size_data["file_size_bytes"] = 0
            file_size_data["note"] = "Document not saved"
        
        return file_size_data
        
    except Exception as e:
        return {"error": str(traceback.format_exc())}

