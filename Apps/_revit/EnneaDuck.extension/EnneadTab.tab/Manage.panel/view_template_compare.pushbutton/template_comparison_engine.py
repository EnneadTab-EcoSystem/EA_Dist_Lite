"""
Template Comparison Engine Module

This module handles the comparison logic for finding differences between view templates,
including special handling for uncontrolled parameters.
"""


class TemplateComparisonEngine:
    """
    Handles comparison logic between view templates.
    
    This class is responsible for comparing template data and finding differences,
    with special priority handling for uncontrolled parameters.
    """
    
    def __init__(self, comparison_data):
        """
        Initialize the comparison engine.
        
        Args:
            comparison_data: Dictionary containing template data for comparison
        """
        self.comparison_data = comparison_data
    
    def find_all_differences(self, template_names):
        """
        Find all differences between templates.
        
        Args:
            template_names: List of template names to compare
            
        Returns:
            dict: All differences found, organized by type
        """
        differences = {
            'category_overrides': {},
            'category_visibility': {},
            'workset_visibility': {},
            'view_parameters': {},
            'uncontrolled_parameters': {},
            'filters': {}
        }
        
        # Compare category overrides
        differences['category_overrides'] = self._compare_dict_values('category_overrides', template_names)
        
        # Compare category visibility
        differences['category_visibility'] = self._compare_dict_values('category_visibility', template_names)
        
        # Compare workset visibility
        differences['workset_visibility'] = self._compare_dict_values('workset_visibility', template_names)
        
        # Compare view parameters (controlled)
        differences['view_parameters'] = self._compare_list_values('view_parameters', template_names)
        
        # Compare uncontrolled parameters (DANGEROUS - can cause inconsistencies)
        # Based on Revit API: GetNonControlledTemplateParameterIds() returns parameters 
        # that are NOT marked as included when the view is used as a template
        # These can cause inconsistent behavior across views using the same template
        all_uncontrolled_params = set()
        for template_name, data in self.comparison_data.items():
            all_uncontrolled_params.update(data['uncontrolled_parameters'])
            
        for param in all_uncontrolled_params:
            param_values = {}
            for template_name in template_names:
                param_values[template_name] = param in self.comparison_data[template_name]['uncontrolled_parameters']
                    
            if len(set(param_values.values())) > 1:
                differences['uncontrolled_parameters'][param] = param_values
        
        # Compare filters
        differences['filters'] = self._compare_dict_values('filters', template_names)
        
        return differences
    
    def _compare_dict_values(self, data_key, template_names):
        """
        Generic method to compare dictionary values across templates.
        
        Special handling for uncontrolled parameters:
        - If a parameter is uncontrolled in any template, it's marked as "UNCONTROLLED"
        - Uncontrolled parameters are highlighted with dark orange background in HTML
        - This takes priority over normal value comparison
        
        Args:
            data_key: Key in comparison_data to compare
            template_names: List of template names
            
        Returns:
            dict: Differences found
        """
        differences = {}
        
        # Collect all keys from all templates
        all_keys = set()
        for template_name, data in self.comparison_data.items():
            all_keys.update(data[data_key].keys())
        
        # Compare each key across templates
        for key in all_keys:
            key_values = {}
            for template_name in template_names:
                if key in self.comparison_data[template_name][data_key]:
                    key_values[template_name] = self.comparison_data[template_name][data_key][key]
                else:
                    key_values[template_name] = None
            
            # Check if values are different
            if self._has_differences(key_values):
                differences[key] = key_values
        
        return differences
    
    def _compare_list_values(self, data_key, template_names):
        """
        Generic method to compare list values across templates.
        
        Special handling for uncontrolled parameters:
        - If a parameter is uncontrolled in any template, it's marked as "UNCONTROLLED"
        - Uncontrolled parameters are highlighted with dark orange background in HTML
        - This takes priority over normal value comparison
        
        Args:
            data_key: Key in comparison_data to compare
            template_names: List of template names
            
        Returns:
            dict: Differences found
        """
        differences = {}
        
        # Collect all values from all templates
        all_values = set()
        for template_name, data in self.comparison_data.items():
            all_values.update(data[data_key])
        
        # Compare each value across templates
        for value in all_values:
            value_presence = {}
            for template_name in template_names:
                value_presence[template_name] = value in self.comparison_data[template_name][data_key]
            
            # Check if presence is different across templates
            if len(set(value_presence.values())) > 1:
                differences[value] = value_presence
        
        return differences
    
    def _has_differences(self, values_dict):
        """
        Check if values in a dictionary are different.
        
        Args:
            values_dict: Dictionary of values to compare
            
        Returns:
            bool: True if values are different, False if all the same
        """
        values = list(values_dict.values())
        if not values:
            return False
        
        # Check if all values are the same
        first_value = values[0]
        return not all(value == first_value for value in values)
    
    def get_summary_statistics(self, differences):
        """
        Get summary statistics of differences found.
        
        Args:
            differences: Dictionary of differences
            
        Returns:
            dict: Summary statistics
        """
        total_differences = sum(len(diff_dict) for diff_dict in differences.values())
        
        return {
            'total_differences': total_differences,
            'category_overrides': len(differences['category_overrides']),
            'category_visibility': len(differences['category_visibility']),
            'workset_visibility': len(differences['workset_visibility']),
            'view_parameters': len(differences['view_parameters']),
            'uncontrolled_parameters': len(differences['uncontrolled_parameters']),
            'filters': len(differences['filters'])
        } 
    

if __name__ == "__main__":
    pass