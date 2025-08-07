#!/usr/bin/python
# -*- coding: utf-8 -*-

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
proDUCKtion.validify()

from EnneadTab.REVIT import REVIT_APPLICATION
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, TIME
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
    
    # Initialize output and timing
    output = script.get_output()
    time_start = time.time()
    
    output.print_md("# View Template Comparison")
    output.print_md("## Analyzing Templates...")
    
    # Step 2: Collect data from all templates
    comparison_data = collect_template_data(doc, templates)
    
    # Step 3: Find differences between templates
    differences = find_all_differences(comparison_data, [t.Name for t in templates])
    
    # Step 4: Generate and save HTML report
    filepath = generate_and_save_report(differences, [t.Name for t in templates])
    
    # Step 5: Display results and summary
    display_results(differences, filepath, time_start)


def select_templates_for_comparison(doc):
    """
    Select view templates for comparison using PyRevit forms.
    
    Args:
        doc: The Revit document
        
    Returns:
        list: Selected view templates
    """
    # Get all view templates
    collector = DB.FilteredElementCollector(doc).OfClass(DB.View)
    view_templates = [view for view in collector if view.IsTemplate]
    
    if not view_templates:
        ERROR_HANDLE.print_note("No view templates found in the document.")
        return None
    
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
            'filters': collector.get_filter_data(template)
        }
        comparison_data[template.Name] = template_data
    
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


def generate_and_save_report(differences, template_names):
    """
    Generate HTML report and save to file.
    
    Args:
        differences: Dictionary containing all differences
        template_names: List of template names
        
    Returns:
        str: Filepath of the saved HTML report
    """
    # Initialize HTML report generator
    generator = HTMLReportGenerator(template_names)
    
    # Get summary statistics
    engine = TemplateComparisonEngine({})  # Empty dict since we only need the method
    summary_stats = engine.get_summary_statistics(differences)
    
    # Generate HTML report
    html_content = generator.generate_comparison_report(differences, summary_stats)
    
    # Save report to file
    filepath = generator.save_report_to_file(html_content)
    
    return filepath


def display_results(differences, filepath, time_start):
    """
    Display comparison results and summary.
    
    Args:
        differences: Dictionary containing all differences
        filepath: Filepath of the saved HTML report
        time_start: Start time for performance measurement
    """
    output = script.get_output()
    
    # Calculate processing time
    time_diff = time.time() - time_start
    
    # Get summary statistics
    engine = TemplateComparisonEngine({})
    summary_stats = engine.get_summary_statistics(differences)
    
    # Display summary
    output.print_md("## Summary")
    output.print_md("**Templates compared:** {}".format(len(differences.get('category_overrides', {}))))
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


# Main execution
if __name__ == "__main__":
    compare_view_templates(DOC) 