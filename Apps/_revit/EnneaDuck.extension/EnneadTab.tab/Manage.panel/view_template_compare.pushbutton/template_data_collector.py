"""
Template Data Collector Module

This module handles all data collection operations for view templates,
including category overrides, visibility settings, worksets, parameters, and filters.
"""

import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitServices')
import Autodesk.Revit.DB as DB
from Autodesk.Revit.DB import *

from pyrevit import forms
from pyrevit import script

from EnneadTab import ERROR_HANDLE
from EnneadTab.REVIT import REVIT_CATEGORY


class TemplateDataCollector:
    """
    Handles data collection from view templates.
    
    This class is responsible for extracting all relevant data from view templates
    including category overrides, visibility settings, worksets, parameters, and filters.
    """
    
    def __init__(self, doc):
        """
        Initialize the data collector.
        
        Args:
            doc: The Revit document
        """
        self.doc = doc
        self.categories = self._get_sorted_categories()
    
    def _get_sorted_categories(self):
        """
        Get all categories and subcategories sorted alphabetically.
        
        Returns:
            list: Sorted list of category objects with pretty names
        """
        categories = []
        
        # Get all categories
        for category in self.doc.Settings.Categories:
            if category.AllowsBoundParameters:
                # Add main category
                categories.append({
                    'category': category,
                    'pretty_name': category.Name,
                    'is_subcategory': False
                })
                
                # Add subcategories
                for subcategory in category.SubCategories:
                    if subcategory.AllowsBoundParameters:
                        categories.append({
                            'category': subcategory,
                            'pretty_name': "{} - {}".format(category.Name, subcategory.Name),
                            'is_subcategory': True
                        })
        
        # Sort by pretty name
        return sorted(categories, key=lambda x: x['pretty_name'])
    
    def get_category_overrides(self, template):
        """
        Extract category override settings from a template.
        
        Improved error handling:
        - Checks if category allows bound parameters before attempting override
        - Uses ERROR_HANDLE.print_note for detailed error reporting
        - Provides summary of skipped categories
        - Uses explicit exception handling instead of silent try-catch
        
        Args:
            template: The view template to analyze
            
        Returns:
            dict: Category override settings with readable pattern names
        """
        overrides = {}
        skipped_categories = []
        
        for category in self.categories:
            # Pre-check if category allows bound parameters
            if not category['category'].AllowsBoundParameters:
                continue
                
            try:
                override = template.GetCategoryOverrides(category['category'].Id)
                if override:
                    overrides[category['pretty_name']] = self._extract_override_details(override)
            except Exception as e:
                # Log specific error for debugging
                error_msg = "Failed to get override for category '{}': {}".format(category['pretty_name'], str(e))
                skipped_categories.append(error_msg)
                ERROR_HANDLE.print_note(error_msg)
                continue
                
        # Log summary of skipped categories if any
        if skipped_categories:
            summary_msg = "Skipped {} categories during override extraction: {}".format(
                len(skipped_categories), ", ".join(skipped_categories[:5])  # Show first 5
            )
            ERROR_HANDLE.print_note(summary_msg)
            
        return overrides
    
    def _extract_override_details(self, override):
        """
        Extract detailed override information from OverrideGraphicSettings.
        
        Args:
            override: OverrideGraphicSettings object
            
        Returns:
            dict: Detailed override information
        """
        details = {}
        
        # Halftone
        details['halftone'] = override.Halftone
        
        # Line weight
        details['line_weight'] = override.LineWeight
        
        # Line color
        line_color = override.LineColor
        details['line_color'] = self._format_color(line_color)
        
        # Line pattern
        details['line_pattern'] = self._get_pattern_name(override.LinePatternId)
        
        # Cut line weight
        details['cut_line_weight'] = override.CutLineWeight
        
        # Cut line color
        cut_line_color = override.CutLineColor
        details['cut_line_color'] = self._format_color(cut_line_color)
        
        # Cut line pattern
        details['cut_line_pattern'] = self._get_pattern_name(override.CutLinePatternId)
        
        # Cut fill pattern
        details['cut_fill_pattern'] = self._get_pattern_name(override.CutFillPatternId)
        
        # Cut fill color
        cut_fill_color = override.CutFillColor
        details['cut_fill_color'] = self._format_color(cut_fill_color)
        
        # Projection fill pattern
        details['projection_fill_pattern'] = self._get_pattern_name(override.ProjectionFillPatternId)
        
        # Projection fill color
        projection_fill_color = override.ProjectionFillColor
        details['projection_fill_color'] = self._format_color(projection_fill_color)
        
        # Transparency
        details['transparency'] = override.Transparency
        
        return details
    
    def _get_pattern_name(self, pattern_id):
        """
        Get readable pattern name from pattern ID.
        
        Args:
            pattern_id: The ElementId of the pattern
            
        Returns:
            str: Pattern name or "Default" if not found
        """
        if pattern_id == DB.ElementId.InvalidElementId:
            return "Default"
        
        try:
            pattern = self.doc.GetElement(pattern_id)
            if pattern:
                return pattern.Name
            else:
                ERROR_HANDLE.print_note("Pattern element not found for ID: {}".format(pattern_id))
                return "Default"
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to get pattern name for ID {}: {}".format(pattern_id, str(e)))
            return "Default"
    
    def _format_color(self, color):
        """
        Format color as RGB string.
        
        Args:
            color: Color object
            
        Returns:
            str: RGB color string
        """
        if color:
            return "RGB({}, {}, {})".format(color.Red, color.Green, color.Blue)
        return "Default"
    
    def get_category_visibility(self, template):
        """
        Get category visibility settings from template.
        
        Improved error handling:
        - Checks if category allows bound parameters before attempting visibility check
        - Uses ERROR_HANDLE.print_note for detailed error reporting
        - Provides summary of skipped categories
        - Uses explicit exception handling instead of silent try-catch
        
        Args:
            template: The view template to analyze
            
        Returns:
            dict: Category visibility settings (On/Off)
        """
        visibility = {}
        skipped_categories = []
        
        for category in self.categories:
            # Pre-check if category allows bound parameters
            if not category['category'].AllowsBoundParameters:
                continue
                
            try:
                is_hidden = template.GetCategoryHidden(category['category'].Id)
                visibility[category['pretty_name']] = "Off" if is_hidden else "On"
            except Exception as e:
                error_msg = "Failed to get visibility for category '{}': {}".format(category['pretty_name'], str(e))
                skipped_categories.append(error_msg)
                ERROR_HANDLE.print_note(error_msg)
                continue
                    
        # Log summary of skipped categories if any
        if skipped_categories:
            summary_msg = "Skipped {} categories during visibility extraction: {}".format(
                len(skipped_categories), ", ".join(skipped_categories[:5])
            )
            ERROR_HANDLE.print_note(summary_msg)
            
        return visibility
    
    def get_workset_visibility(self, template):
        """
        Get workset visibility settings from template.
        
        Improved error handling:
        - Uses FilteredWorksetCollector for proper workset collection
        - Uses ERROR_HANDLE.print_note for detailed error reporting
        - Provides summary of skipped worksets
        - Uses explicit exception handling instead of silent try-catch
        
        Args:
            template: The view template to analyze
            
        Returns:
            dict: Workset visibility settings with readable text
        """
        worksets = {}
        skipped_worksets = []
        
        workset_collector = DB.FilteredWorksetCollector(self.doc).OfKind(DB.WorksetKind.UserWorkset)
        
        for workset in workset_collector:
            try:
                visibility = template.GetWorksetVisibility(workset.Id)
                worksets[workset.Name] = self._convert_visibility_to_text(visibility)
            except Exception as e:
                error_msg = "Failed to get visibility for workset '{}': {}".format(workset.Name, str(e))
                skipped_worksets.append(error_msg)
                ERROR_HANDLE.print_note(error_msg)
                continue
                    
        # Log summary of skipped worksets if any
        if skipped_worksets:
            summary_msg = "Skipped {} worksets during visibility extraction: {}".format(
                len(skipped_worksets), ", ".join(skipped_worksets[:5])
            )
            ERROR_HANDLE.print_note(summary_msg)
            
        return worksets
    
    def _convert_visibility_to_text(self, visibility):
        """
        Convert workset visibility enum to readable text.
        
        Args:
            visibility: WorksetVisibility enum value
            
        Returns:
            str: Readable visibility text
        """
        if visibility == DB.WorksetVisibility.Visible:
            return "Visible"
        elif visibility == DB.WorksetVisibility.Hidden:
            return "Hidden"
        else:
            return "UseGlobalSetting"
    
    def get_view_parameters(self, template):
        """
        Get view parameters controlled by template.
        
        Args:
            template: The view template to analyze
            
        Returns:
            tuple: (controlled_params, uncontrolled_params)
        """
        controlled_params = []
        uncontrolled_params = []
        
        # Get non-controlled parameter IDs
        param_ids = template.GetNonControlledTemplateParameterIds()
        
        # Get all view parameters
        for param in template.Parameters:
            if param.Id not in param_ids:
                controlled_params.append(param.Definition.Name)
            else:
                uncontrolled_params.append(param.Definition.Name)
                
        return controlled_params, uncontrolled_params
    
    def get_filter_data(self, template):
        """
        Get filter usage and graphic override data.
        
        Improved error handling:
        - Uses ERROR_HANDLE.print_note for detailed error reporting
        - Provides summary of skipped filters
        - Uses explicit exception handling instead of silent try-catch
        
        Args:
            template: The view template to analyze
            
        Returns:
            dict: Filter data with override settings
        """
        filters = {}
        skipped_filters = []
        
        filter_ids = template.GetFilters()
        
        for filter_id in filter_ids:
            try:
                filter_element = self.doc.GetElement(filter_id)
                if filter_element:
                    override = template.GetFilterOverrides(filter_id)
                    filters[filter_element.Name] = self._extract_filter_override_details(override)
            except Exception as e:
                error_msg = "Failed to get filter data for ID {}: {}".format(filter_id, str(e))
                skipped_filters.append(error_msg)
                ERROR_HANDLE.print_note(error_msg)
                continue
                
        # Log summary of skipped filters if any
        if skipped_filters:
            summary_msg = "Skipped {} filters during extraction: {}".format(
                len(skipped_filters), ", ".join(skipped_filters[:5])
            )
            ERROR_HANDLE.print_note(summary_msg)
            
        return filters
    
    def _extract_filter_override_details(self, override):
        """
        Extract filter override details.
        
        Args:
            override: OverrideGraphicSettings object for filter
            
        Returns:
            dict: Filter override details
        """
        details = {}
        
        # Halftone
        details['halftone'] = override.Halftone
        
        # Line weight
        details['line_weight'] = override.LineWeight
        
        # Line color
        line_color = override.LineColor
        details['line_color'] = self._format_color(line_color)
        
        # Line pattern
        details['line_pattern'] = self._get_pattern_name(override.LinePatternId)
        
        # Cut line weight
        details['cut_line_weight'] = override.CutLineWeight
        
        # Cut line color
        cut_line_color = override.CutLineColor
        details['cut_line_color'] = self._format_color(cut_line_color)
        
        # Cut line pattern
        details['cut_line_pattern'] = self._get_pattern_name(override.CutLinePatternId)
        
        # Cut fill pattern
        details['cut_fill_pattern'] = self._get_pattern_name(override.CutFillPatternId)
        
        # Cut fill color
        cut_fill_color = override.CutFillColor
        details['cut_fill_color'] = self._format_color(cut_fill_color)
        
        # Projection fill pattern
        details['projection_fill_pattern'] = self._get_pattern_name(override.ProjectionFillPatternId)
        
        # Projection fill color
        projection_fill_color = override.ProjectionFillColor
        details['projection_fill_color'] = self._format_color(projection_fill_color)
        
        # Transparency
        details['transparency'] = override.Transparency
        
        return details 
    


if __name__ == "__main__":
    pass