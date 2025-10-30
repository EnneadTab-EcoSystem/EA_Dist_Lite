#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Family hierarchy visualization tool that reveals the complete nesting structure of complex Revit families. This utility generates an interactive HTML visualization with D3.js, showing parent-child relationships, parameter details, and parameter associations between families. Click any family node to see comprehensive parameter information including types, storage types, formulas, and values across all family types.

Works in both Project and Family documents. In projects, you can select families to analyze.

Features:
- Preview images for all family types with dropdown selector
- Parameters grouped by Revit parameter groups
- Built-in vs user-created parameter detection (INVALID = user-created)
- Material parameter identification
- Animated flowing connections showing hierarchy
- 40+ category colors with hot pink alert for unknown
- Document units (feet, inches, millimeters)
- Creator and last editor tracking
- Shared vs standard family detection

API References:
- FamilyParameter: https://www.revitapidocs.com/2015/6175e974-870e-7fbc-3df7-46105f937a6e.htm
- FamilyManager: https://www.revitapidocs.com/2015/1cc4fe6c-0e9f-7439-0021-32d2e06f4c33.htm
"""
__title__ = "Family\nTree"
__tip__ = True

import sys
import os

# Add current directory to path for module imports
script_dir = os.path.dirname(__file__)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS
from EnneadTab import ERROR_HANDLE, EXE, FOLDER, LOG, NOTIFICATION
from Autodesk.Revit import DB # pyright: ignore
from pyrevit import forms # pyright: ignore

# Import our modular components
try:
    from family_data_extractor import FamilyDataExtractor
    from family_html_generator import FamilyTreeHTMLGenerator
except ImportError as e:
    print("ERROR: Failed to import modules: {}".format(e))
    print("Script directory: {}".format(script_dir))
    print("sys.path: {}".format(sys.path))
    raise

doc = REVIT_APPLICATION.get_doc()
uidoc = REVIT_APPLICATION.get_uidoc()


def open_html_in_browser(html_path):
    """Open HTML file in browser, trying Edge first, then Chrome, then default.
    
    Args:
        html_path: Path to HTML file
        
    Returns:
        bool: True if successfully opened
    """
    import subprocess
    
    # Try Edge first (Microsoft Edge is common on Windows)
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    
    for edge_path in edge_paths:
        if os.path.exists(edge_path):
            try:
                subprocess.Popen([edge_path, html_path])
                return True
            except Exception:
                pass
    
    # Try Chrome second
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    
    for chrome_path in chrome_paths:
        if os.path.exists(chrome_path):
            try:
                subprocess.Popen([chrome_path, html_path])
                return True
            except Exception:
                pass
    
    # Fall back to default system handler
    try:
        os.startfile(html_path)
        return True
    except Exception:
        return False


def get_all_families_in_project(doc):
    """Get all loadable families in the project.
    
    Args:
        doc: Revit document
        
    Returns:
        list: List of Family objects sorted by category and name
    """
    families = list(DB.FilteredElementCollector(doc).OfClass(DB.Family).ToElements())
    
    # Filter to only editable families (exclude system families)
    loadable_families = [f for f in families if f.IsEditable]
    
    # Sort by category then name
    loadable_families.sort(key=lambda f: "{}_{}".format(
        f.FamilyCategory.Name if f.FamilyCategory else "Unknown",
        f.Name
    ))
    
    return loadable_families


def select_families_from_project(doc):
    """Show family selection UI for project documents.
    
    Args:
        doc: Revit document
        
    Returns:
        list: List of selected Family objects, or None if cancelled
    """
    families = get_all_families_in_project(doc)
    
    if not families:
        NOTIFICATION.messenger("No loadable families found in this project!")
        return None
    
    # Create selection options with category prefix
    family_options = []
    for family in families:
        category = family.FamilyCategory.Name if family.FamilyCategory else "Unknown"
        option_name = "[{}] {}".format(category, family.Name)
        family_options.append(option_name)
    
    # Show selection dialog
    selected_names = forms.SelectFromList.show(
        family_options,
        title="Select Families to Analyze",
        width=600,
        height=600,
        button_name="Analyze Selected",
        multiselect=True
    )
    
    if not selected_names:
        return None
    
    # Map back to Family objects
    selected_families = []
    for selected_name in selected_names:
        index = family_options.index(selected_name)
        selected_families.append(families[index])
    
    return selected_families


class Solution:
    """Main orchestrator for family tree visualization."""
    
    @ERROR_HANDLE.try_catch_error()
    def family_tree(self):
        """Generate interactive family tree visualization."""
        
        try:
            # Determine if we're in a family document or project document
            is_family_doc = doc.IsFamilyDocument
            
            if is_family_doc:
                # Direct analysis of current family document
                families_to_analyze = [(doc, doc.Title, False)]  # (doc, name, should_close)
            else:
                # Project document - let user select families
                selected_families = select_families_from_project(doc)
                
                if not selected_families:
                    return
                
                # Open each family for analysis
                families_to_analyze = []
                for family in selected_families:
                    try:
                        family_doc = doc.EditFamily(family)
                        families_to_analyze.append((family_doc, family.Name, True))  # Should close after
                    except Exception as e:
                        NOTIFICATION.messenger("Warning: Could not open family '{}'\n\nError: {}".format(family.Name, str(e)))
            
            if not families_to_analyze:
                NOTIFICATION.messenger("No families could be opened for analysis.")
                return
            
            # Show starting message
            NOTIFICATION.messenger("Analyzing {} family tree(s)...\n\nThis may take 30-60 seconds for complex families.\nPlease wait...".format(len(families_to_analyze)))
            
            # Track generated files
            generated_files = []
            failed_families = []
            
            # Analyze each family
            for idx, (family_doc, family_name, should_close) in enumerate(families_to_analyze, 1):
                try:
                    # Extract family data
                    extractor = FamilyDataExtractor()
                    tree_data = extractor.extract_family_tree(family_doc)
                    
                    # Generate HTML visualization
                    generator = FamilyTreeHTMLGenerator(tree_data)
                    dest_file = FOLDER.get_local_dump_folder_file(
                        "Family Tree of {}.html".format(family_name)
                    )
                    generator.generate_html(dest_file)
                    
                    # Track successful generation
                    generated_files.append({
                        "name": family_name,
                        "file": dest_file,
                        "nodes": len(tree_data.get("nodes", [])),
                        "links": len(tree_data.get("links", []))
                    })
                    
                    # Cleanup - close nested family documents
                    extractor.cleanup_documents()
                    
                    # Close the main family document if from project
                    if should_close:
                        family_doc.Close(False)
                    
                except Exception as e:
                    # Track failed family
                    failed_families.append({
                        "name": family_name,
                        "error": str(e)
                    })
                    
                    # Close the family document if needed
                    if should_close:
                        try:
                            family_doc.Close(False)
                        except:
                            pass
            
            # Create summary message
            if generated_files:
                # Open ALL generated files in browser (each in a new tab)
                for gen_file in generated_files:
                    open_html_in_browser(gen_file["file"])
                
                # Build summary message
                summary_lines = ["Family Tree Analysis Complete!\n"]
                summary_lines.append("=" * 50)
                summary_lines.append("\nSuccessfully Generated ({} families):\n".format(len(generated_files)))
                
                for gen_file in generated_files:
                    summary_lines.append("  ✓ {}: {} families, {} relationships".format(
                        gen_file["name"],
                        gen_file["nodes"],
                        gen_file["links"]
                    ))
                
                if failed_families:
                    summary_lines.append("\n\nFailed ({} families):\n".format(len(failed_families)))
                    for failed in failed_families:
                        summary_lines.append("  ✗ {}: {}".format(
                            failed["name"],
                            failed["error"][:60]
                        ))
                
                summary_lines.append("\n" + "=" * 50)
                summary_lines.append("\nAll HTML files saved to:")
                folder_path = os.path.dirname(generated_files[0]["file"])
                summary_lines.append(folder_path)
                
                summary_msg = "\n".join(summary_lines)
                
                # Show in both output window and notification popup
                print("\n" + summary_msg)
                NOTIFICATION.messenger(summary_msg)
                
                # Open the folder
                EXE.try_open_app(folder_path)
            else:
                # All failed
                error_msg = "All family tree generations failed!\n\nFailed families:\n"
                for failed in failed_families:
                    error_msg += "  ✗ {}: {}\n".format(failed["name"], failed["error"][:60])
                
                # Show in both output window and notification popup
                print("\n" + error_msg)
                NOTIFICATION.messenger(error_msg)
            
        except Exception as e:
            error_msg = "Family tree generation failed!\n\nError: {}".format(str(e))
            NOTIFICATION.messenger(error_msg)
            raise


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    Solution().family_tree()
    
################## main code below #####################


if __name__ == "__main__":
    main()
    
