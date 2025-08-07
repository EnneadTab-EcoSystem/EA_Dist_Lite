#!/usr/bin/python
# -*- coding: utf-8 -*-
# IronPython 2.7 Compatible

__doc__ = """Compare multiple view templates and generate an interactive HTML report showing differences.
This tool allows users to select multiple view templates and compares their settings including:
- Category overrides (visibility, halftone, line weight, color, etc.)
- Category visibility settings
- Workset visibility
- View parameters (controlled and uncontrolled)
- Filter usage and graphic overrides

The output is an interactive HTML table where columns represent each template and rows show differences.
Uncontrolled parameters are highlighted as dangerous since they can cause inconsistencies."""
__title__ = "View Template\nCompare"
__tip__ = True

from pyrevit import forms
from pyrevit import script
import proDUCKtion
import time
import os
proDUCKtion.validify()

from EnneadTab.REVIT import REVIT_APPLICATION
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, TIME, USER, DATA_FILE, FOLDER
from Autodesk.Revit import DB

DOC = REVIT_APPLICATION.get_doc()

# Import our modular components
from template_data_collector import TemplateDataCollector
from template_comparison_engine import TemplateComparisonEngine
from html_report_generator import HTMLReportGenerator


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def compare_view_templates(doc):
    """
    Main function to compare view templates.
    
    This function orchestrates the entire comparison process:
    1. Template selection
    2. Data collection
    3. Comparison analysis
    4. Report generation
    5. Results display
    """
    # Get Revit document
    if not doc:
        ERROR_HANDLE.print_note("No active Revit document found.")
        return
    
    # Step 1: Select templates for comparison
    templates = select_templates_for_comparison(doc)
    if not templates or len(templates) < 2:
        ERROR_HANDLE.print_note("Please select at least 2 view templates for comparison.")
        return
    
    # Validate templates before processing
    valid_templates = validate_templates(templates)
    if not valid_templates or len(valid_templates) < 2:
        ERROR_HANDLE.print_note("No valid templates found for comparison.")
        return
    
    # Initialize output and timing
    output = script.get_output()
    time_start = time.time()
    
    output.print_md("# View Template Comparison")
    output.print_md("## Analyzing Templates...")
    
    # Step 2: Collect data from all templates with timeout protection
    result = collect_template_data_with_timeout(doc, valid_templates, output)
    if not result or not result[0]:
        ERROR_HANDLE.print_note("Failed to collect template data. Please try again.")
        return
    
    comparison_data, full_template_data = result
    
    # Step 3: Find differences between templates
    differences = find_all_differences(comparison_data, [t.Name for t in valid_templates])
    
    # Step 4: Save full template data as JSON and get file path
    json_file_path = save_full_template_data_as_json(full_template_data, doc)
    
    # Step 5: Generate and save HTML report
    filepath = generate_and_save_report(differences, [t.Name for t in valid_templates], comparison_data, json_file_path)
    
    # Step 5: Display results and summary
    display_results(differences, filepath, time_start, [t.Name for t in valid_templates])


def validate_templates(templates):
    """
    Validate templates to ensure they are still valid and accessible.
    
    Args:
        templates: List of view templates to validate
        
    Returns:
        list: Valid templates only
    """
    valid_templates = []
    
    for template in templates:
        try:
            # Check if template is still valid
            if template and template.IsValidObject:
                # Try to access a basic property to ensure it's accessible
                template_name = template.Name
                if template_name:
                    valid_templates.append(template)
                else:
                    ERROR_HANDLE.print_note("Template has no name, skipping: {}".format(template.Id))
            else:
                ERROR_HANDLE.print_note("Template is no longer valid, skipping: {}".format(template.Id))
        except Exception as e:
            ERROR_HANDLE.print_note("Error validating template {}: {}".format(template.Id, str(e)))
            continue
    
    return valid_templates


def collect_template_data_with_timeout(doc, templates, output):
    """
    Collect data from all selected templates with timeout protection.
    
    Args:
        doc: The Revit document
        templates: List of view templates to analyze
        output: PyRevit output object for progress reporting
        
    Returns:
        dict: Collected data for all templates or None if timeout
    """
    # Initialize data collector
    collector = TemplateDataCollector(doc)
    comparison_data = {}
    full_template_data = {}  # For JSON dump
    
    # Set timeout (5 minutes)
    timeout_seconds = 300
    start_time = time.time()
    
    # Collect data for each template with progress reporting
    for i, template in enumerate(templates):
        # Check timeout
        if time.time() - start_time > timeout_seconds:
            ERROR_HANDLE.print_note("Data collection timed out after {} seconds. Please try with fewer templates.".format(timeout_seconds))
            return None
        
        try:
            output.print_md("**Processing template {}/{}: {}**".format(i+1, len(templates), template.Name))
            
            # Collect data with individual timeout for each template
            template_start_time = time.time()
            template_timeout = 60  # 1 minute per template
            
            # Use comprehensive data collection method
            full_data = collector.collect_all_template_data(template)
            
            # Check individual template timeout
            if time.time() - template_start_time > template_timeout:
                ERROR_HANDLE.print_note("Template {} timed out, skipping.".format(template.Name))
                continue
            
            if full_data:
                # Store full data for JSON dump
                full_template_data[template.Name] = full_data
                
                # Create data for comparison
                template_data = {
                    'name': full_data['template_name'],
                    'category_overrides': full_data['category_overrides'],
                    'category_visibility': full_data['category_visibility'],
                    'workset_visibility': full_data['workset_visibility'],
                    'view_parameters': full_data['view_parameters'],
                    'uncontrolled_parameters': full_data['uncontrolled_parameters'],
                    'filters': full_data['filters'],
                    'import_categories': full_data['import_categories'],
                    'revit_links': full_data['revit_links'],
                    'detail_levels': full_data['detail_levels'],
                    'view_properties': full_data['view_properties'],
                    'template_usage': full_data['template_usage']
                }
                
                comparison_data[template.Name] = template_data
            
            # Check timeout again after data collection
            if time.time() - template_start_time > template_timeout:
                ERROR_HANDLE.print_note("Template {} data collection timed out, using partial data.".format(template.Name))
            
        except Exception as e:
            ERROR_HANDLE.print_note("Error processing template {}: {}".format(template.Name, str(e)))
            continue
    
    # Save full template data as JSON for developer use
    ERROR_HANDLE.print_note("About to save JSON data. Full template data keys: {}".format(list(full_template_data.keys()) if full_template_data else "None"))
    save_full_template_data_as_json(full_template_data, doc)
    
    # Save error data if any errors occurred
    template_names_str = "_".join([t.Name for t in templates[:2]])  # Use first 2 template names
    collector.save_error_data(template_names_str)
    
    return (comparison_data if comparison_data else None, full_template_data)


def select_templates_for_comparison(doc):
    """
    Select view templates for comparison using PyRevit forms.
    
    Args:
        doc: The Revit document
        
    Returns:
        list: Selected view templates
    """
    try:
        # Get all view templates with error handling
        collector = DB.FilteredElementCollector(doc).OfClass(DB.View)
        view_templates = []
        
        for view in collector:
            try:
                if view and view.IsTemplate and view.IsValidObject:
                    view_templates.append(view)
            except Exception as e:
                ERROR_HANDLE.print_note("Error checking view template: {}".format(str(e)))
                continue
        
        if not view_templates:
            ERROR_HANDLE.print_note("No view templates found in the document.")
            return None
        



        
        # If in DEVELOPER mode, automatically select test templates
        # if USER.IS_DEVELOPER:
        #     test_templates = []
        #     for template in view_templates:
        #         if "0__test1" in template.Name or "0__test2" in template.Name:
        #             test_templates.append(template)

            
        #     if len(test_templates) >= 2:
        #         ERROR_HANDLE.print_note("DEVELOPER mode: Auto-selected test templates: {}".format([t.Name for t in test_templates]))
        #         return test_templates
        #     elif len(test_templates) == 1:
        #         ERROR_HANDLE.print_note("DEVELOPER mode: Only found 1 test template ({}), proceeding with manual selection".format(test_templates[0].Name))
        #     else:
        #         ERROR_HANDLE.print_note("DEVELOPER mode: No test templates found, proceeding with manual selection")
        #     return test_templates
        
        # Create custom template list items for selection that show template names
        class TemplateOption(forms.TemplateListItem):
            @property
            def name(self):
                return self.item.Name
        
        template_items = sorted([TemplateOption(template) for template in view_templates], key=lambda x: x.name)
        
        # Show selection dialog
        selected_templates = forms.SelectFromList.show(
            template_items,
            title="Select View Templates to Compare",
            multiselect=True,
            button_name="Compare Templates"
        )
        
        if not selected_templates:
            return None
        
        return selected_templates
        
    except Exception as e:
        ERROR_HANDLE.print_note("Error selecting templates: {}".format(str(e)))
        return None


def collect_template_data(doc, templates):
    """
    Collect data from all selected templates.
    
    Args:
        doc: The Revit document
        templates: List of view templates to analyze
        
    Returns:
        dict: Collected data for all templates
    """
    # Initialize data collector
    collector = TemplateDataCollector(doc)
    comparison_data = {}
    
    # Collect data for each template
    for template in templates:
        controlled_params, uncontrolled_params = collector.get_view_parameters(template)
        template_data = {
            'name': template.Name,
            'category_overrides': collector.get_category_overrides(template),
            'category_visibility': collector.get_category_visibility(template),
            'workset_visibility': collector.get_workset_visibility(template),
            'view_parameters': controlled_params,
            'uncontrolled_parameters': uncontrolled_params,
            'filters': collector.get_filter_data(template),
            'import_categories': collector.get_import_category_data(template),
            'revit_links': collector.get_revit_link_data(template),
            'detail_levels': collector.get_detail_level_data(template),
            'view_properties': collector._get_view_properties(template)
        }
        comparison_data[template.Name] = template_data
    
    # Save error data if any errors occurred
    template_names_str = "_".join([t.Name for t in templates[:2]])  # Use first 2 template names
    collector.save_error_data(template_names_str)
    
    return comparison_data


def find_all_differences(comparison_data, template_names):
    """
    Find all differences between templates using the comparison engine.
    
    Args:
        comparison_data: Dictionary containing template data
        template_names: List of template names
        
    Returns:
        dict: All differences found
    """
    # Initialize comparison engine
    engine = TemplateComparisonEngine(comparison_data)
    
    # Find all differences
    differences = engine.find_all_differences(template_names)
    
    return differences


def generate_and_save_report(differences, template_names, comparison_data=None, json_file_path=None):
    """
    Generate HTML report and save to file.
    
    Args:
        differences: Dictionary containing all differences
        template_names: List of template names
        comparison_data: Dictionary containing all template data for comprehensive comparison
        json_file_path: Path to the saved JSON file for clickable link
        
    Returns:
        str: Filepath of the saved HTML report
    """
    # Initialize HTML report generator
    generator = HTMLReportGenerator(template_names)
    
    # Get summary statistics
    engine = TemplateComparisonEngine({})  # Empty dict since we only need the method
    summary_stats = engine.get_summary_statistics(differences)
    
    # Generate HTML report
    html_content = generator.generate_comparison_report(differences, summary_stats, comparison_data, json_file_path)
    
    # Save report to file
    filepath = generator.save_report_to_file(html_content)
    
    return filepath


def display_results(differences, filepath, time_start, template_names=None):
    """
    Display comparison results and summary.
    
    Args:
        differences: Dictionary containing all differences
        filepath: Filepath of the saved HTML report
        time_start: Start time for performance measurement
        template_names: List of template names that were compared
    """
    output = script.get_output()
    
    # Calculate processing time
    time_diff = time.time() - time_start
    
    # Get summary statistics
    engine = TemplateComparisonEngine({})
    summary_stats = engine.get_summary_statistics(differences)
    
    # Calculate template count correctly
    template_count = len(template_names) if template_names else 0
    if template_count == 0 and differences:
        # Fallback: try to infer from any differences that have template-specific data
        for diff_type, diff_data in differences.items():
            if isinstance(diff_data, dict) and diff_data:
                # Get the first item and count its template entries
                first_item = next(iter(diff_data.values()))
                if isinstance(first_item, dict):
                    template_count = len(first_item)
                    break
    
    # Display summary
    output.print_md("## Summary")
    output.print_md("**Templates compared:** {}".format(template_count))
    output.print_md("**Total differences found:** {}".format(summary_stats['total_differences']))
    output.print_md("**Processing time:** {:.2f} seconds".format(time_diff))
    output.print_md("**Report saved to:** {}".format(filepath))
    
    # Warning about uncontrolled parameters
    if differences.get('uncontrolled_parameters'):
        output.print_md("## **DANGER: Uncontrolled Parameters Found**")
        output.print_md("**{} parameters are uncontrolled across templates.**".format(len(differences['uncontrolled_parameters'])))
        output.print_md("These parameters are NOT marked as included when the view is used as a template.")
        output.print_md("This can cause **inconsistent behavior** across views using the same template.")
        output.print_md("**Review these parameters in the HTML report and consider controlling them if needed.**")
    
    # Open HTML report
    try:
        import os
        os.startfile(filepath)
    except Exception as e:
        ERROR_HANDLE.print_note("Failed to open HTML report: {}".format(str(e)))
    
    # Show completion notification
    NOTIFICATION.messenger("View template comparison completed in {}. Report opened.".format(TIME.get_readable_time(time_diff)))


def save_full_template_data_as_json(full_template_data, doc):
    """
    Save full template data using DATA_FILE.set_data for developer use.
    
    Args:
        full_template_data: Complete template data dictionary
        doc: The Revit document
        
    Returns:
        str: File path to the saved JSON file, or None if failed
    """
    try:
        ERROR_HANDLE.print_note("Starting DATA_FILE save process...")
        ERROR_HANDLE.print_note("Full template data type: {}".format(type(full_template_data)))
        ERROR_HANDLE.print_note("Full template data length: {}".format(len(full_template_data) if full_template_data else 0))
        
        # Create filename with timestamp
        project_name = doc.Title.replace(" ", "_").replace(".", "_") if doc.Title else "Unknown_Project"
        filename = "template_full_data_{}".format(project_name)
        
        # Save using DATA_FILE.set_data (automatically saves to DUMP folder)
        ERROR_HANDLE.print_note("About to save data file: {}".format(filename))
        DATA_FILE.set_data(full_template_data, filename, is_local=True)
        
        ERROR_HANDLE.print_note("Full template data saved using DATA_FILE.set_data to: {}".format(filename))
        
        # Get the file path for the saved JSON file
        filepath = FOLDER.get_local_dump_folder_file(filename)
        
        # Check if DEVELOPER mode is enabled and open JSON file
        if USER.IS_DEVELOPER:
            ERROR_HANDLE.print_note("Opening file for developer: {}".format(filepath))
            if os.path.exists(filepath):
                os.startfile(filepath)
        
        return filepath
            
    except Exception as e:
        ERROR_HANDLE.print_note("Error saving full template data: {}".format(str(e)))
        return None


# Main execution
if __name__ == "__main__":
    compare_view_templates(DOC) 