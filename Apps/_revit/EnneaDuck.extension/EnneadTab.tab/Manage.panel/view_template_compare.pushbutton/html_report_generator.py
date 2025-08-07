# -*- coding: utf-8 -*-
"""
HTML Report Generator Module

This module handles the generation of interactive HTML reports for view template comparisons,
including styling, JavaScript functionality, and organized data presentation.
"""

import os
import tempfile
from datetime import datetime

from EnneadTab import ERROR_HANDLE


class HTMLReportGenerator:
    """
    Generates interactive HTML reports for view template comparisons.
    
    This class is responsible for creating comprehensive, interactive HTML reports
    that display template differences in an organized and visually appealing format.
    """
    
    def __init__(self, template_names):
        """
        Initialize the HTML report generator.
        
        Args:
            template_names: List of template names for the report
        """
        self.template_names = template_names
    
    def generate_comparison_report(self, differences, summary_stats, comparison_data=None):
        """
        Generate the complete HTML comparison report.
        
        Args:
            differences: Dictionary containing all differences found
            summary_stats: Dictionary containing summary statistics
            comparison_data: Dictionary containing all template data for comprehensive comparison
            
        Returns:
            str: Complete HTML report as string
        """
        # Ensure differences and summary_stats are valid dictionaries
        if not isinstance(differences, dict):
            differences = {}
        if not isinstance(summary_stats, dict):
            summary_stats = {}
        if comparison_data is None:
            comparison_data = {}
        
        # Ensure template_names is properly initialized
        if not hasattr(self, 'template_names') or not isinstance(self.template_names, list):
            self.template_names = []
        
        # Validate template_names
        valid_template_names = []
        for name in self.template_names:
            try:
                if name is not None and str(name).strip():
                    valid_template_names.append(str(name).strip())
                else:
                    valid_template_names.append("Unknown Template")
            except Exception as e:
                ERROR_HANDLE.print_note("Error validating template name: {}".format(str(e)))
                valid_template_names.append("Error: Invalid Name")
        
        self.template_names = valid_template_names
        
        html = self._generate_html_header()
        html += self._generate_summary_section(summary_stats)
        html += self._generate_comprehensive_comparison_section(comparison_data)
        html += self._generate_detailed_sections(differences)
        html += self._generate_html_footer()
        
        return html
    
    def _generate_html_header(self):
        """
        Generate the HTML header with CSS and JavaScript.
        
        Returns:
            str: HTML header section
        """
        # Debug: Print template_names to see what we're working with
        ERROR_HANDLE.print_note("Template names: {}".format(self.template_names))
        
        # Ensure template_names is a valid list
        if not isinstance(self.template_names, list):
            self.template_names = []
        
        # Filter out any None or invalid template names
        valid_template_names = []
        for name in self.template_names:
            try:
                if name is not None and str(name).strip():
                    valid_template_names.append(str(name).strip())
                else:
                    valid_template_names.append("Unknown Template")
            except Exception as e:
                ERROR_HANDLE.print_note("Error processing template name: {}".format(str(e)))
                valid_template_names.append("Error: Invalid Name")
        
        # Use the validated template names
        self.template_names = valid_template_names
        
        # Debug: Print validated template names
        ERROR_HANDLE.print_note("Validated template names: {}".format(self.template_names))
        
        # Safely format the timestamp
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            timestamp = "Unknown time"
            ERROR_HANDLE.print_note("Error formatting timestamp: {}".format(str(e)))
        
        # Debug: Print timestamp
        ERROR_HANDLE.print_note("Timestamp: {}".format(timestamp))
        
        # Build HTML block by block
        html_parts = []
        
        # DOCTYPE and HTML start
        html_parts.append("<!DOCTYPE html>")
        html_parts.append("<html>")
        
        # Head section
        html_parts.append("<head>")
        html_parts.append("    <title>View Template Comparison Report</title>")
        
        # CSS styles
        html_parts.append("    <style>")
        html_parts.append("        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%); color: #e0e0e0; min-height: 100vh; }")
        html_parts.append("        .container { max-width: 1400px; margin: 0 auto; background: rgba(30, 30, 46, 0.95); padding: 30px; border-radius: 15px; box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3); backdrop-filter: blur(10px); border: 1px solid rgba(255, 255, 255, 0.1); }")
        html_parts.append("        h1 { color: #00d4ff; text-align: center; border-bottom: 3px solid #00d4ff; padding-bottom: 15px; font-size: 2.5em; text-shadow: 0 0 20px rgba(0, 212, 255, 0.3); margin-bottom: 30px; }")
        html_parts.append("        h2 { color: #00d4ff; cursor: pointer; padding: 15px; background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 212, 255, 0.05) 100%); border-radius: 10px; margin: 15px 0; border: 1px solid rgba(0, 212, 255, 0.2); transition: all 0.3s ease; }")
        html_parts.append("        h2:hover { background: linear-gradient(135deg, rgba(0, 212, 255, 0.2) 0%, rgba(0, 212, 255, 0.1) 100%); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 212, 255, 0.2); }")
        html_parts.append("        .collapsible { display: none; padding: 20px; border: 1px solid rgba(0, 212, 255, 0.2); border-radius: 10px; margin: 10px 0; background: rgba(30, 30, 46, 0.7); }")
        html_parts.append("        table { width: 100%; border-collapse: collapse; margin: 15px 0; background: rgba(30, 30, 46, 0.8); border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2); }")
        html_parts.append("        th, td { border: 1px solid rgba(0, 212, 255, 0.2); padding: 12px; text-align: left; }")
        html_parts.append("        th { background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); color: #1e1e2e; font-weight: bold; text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3); }")
        html_parts.append("        .template-col { background: linear-gradient(135deg, rgba(255, 107, 107, 0.1) 0%, rgba(255, 107, 107, 0.05) 100%); font-weight: bold; color: #ff6b6b; border-left: 3px solid #ff6b6b; }")
        html_parts.append("        .same { background: linear-gradient(135deg, rgba(46, 213, 115, 0.2) 0%, rgba(46, 213, 115, 0.1) 100%); color: #2ed573; border: 1px solid rgba(46, 213, 115, 0.3); }")
        html_parts.append("        .different { background: linear-gradient(135deg, rgba(255, 165, 2, 0.2) 0%, rgba(255, 165, 2, 0.1) 100%); color: #ffa502; border: 1px solid rgba(255, 165, 2, 0.3); }")
        html_parts.append("        .summary { background: linear-gradient(135deg, rgba(0, 212, 255, 0.1) 0%, rgba(0, 212, 255, 0.05) 100%); padding: 25px; border-radius: 15px; margin: 20px 0; border: 1px solid rgba(0, 212, 255, 0.2); }")
        html_parts.append("        .warning { background: linear-gradient(135deg, rgba(255, 107, 107, 0.2) 0%, rgba(255, 107, 107, 0.1) 100%); border: 2px solid #ff6b6b; padding: 15px; margin-bottom: 20px; border-radius: 10px; }")
        html_parts.append("        .timestamp { color: #a0a0a0; font-size: 0.9em; text-align: center; margin: 15px 0; font-style: italic; }")
        html_parts.append("        .search-container { position: fixed; top: 0; left: 0; right: 0; background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%); padding: 15px; z-index: 1000; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4); border-bottom: 1px solid rgba(0, 212, 255, 0.3); backdrop-filter: blur(10px); }")
        html_parts.append("        .search-container input { width: 350px; padding: 12px 16px; border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 8px; font-size: 14px; margin-right: 12px; background: rgba(30, 30, 46, 0.8); color: #e0e0e0; transition: all 0.3s ease; }")
        html_parts.append("        .search-container input:focus { outline: none; border-color: #00d4ff; box-shadow: 0 0 15px rgba(0, 212, 255, 0.3); background: rgba(30, 30, 46, 0.9); }")
        html_parts.append("        .search-container input::placeholder { color: #a0a0a0; }")
        html_parts.append("        .search-container button { padding: 12px 20px; background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); color: #1e1e2e; border: none; border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.3s ease; margin-right: 8px; }")
        html_parts.append("        .search-container button:hover { background: linear-gradient(135deg, #0099cc 0%, #0077aa 100%); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(0, 212, 255, 0.3); }")
        html_parts.append("        .search-container .search-info { color: #00d4ff; font-size: 13px; margin-left: 15px; font-weight: 500; }")
        html_parts.append("        body { padding-top: 80px; }")
        html_parts.append("        .search-highlight { background: linear-gradient(135deg, #ffd700 0%, #ffed4e 100%); color: #1e1e2e; font-weight: bold; padding: 2px 4px; border-radius: 4px; box-shadow: 0 2px 8px rgba(255, 215, 0, 0.3); }")
        html_parts.append("        .search-hidden { display: none; }")
        html_parts.append("        ul { list-style: none; padding: 0; }")
        html_parts.append("        ul li { padding: 8px 0; border-bottom: 1px solid rgba(0, 212, 255, 0.1); color: #e0e0e0; }")
        html_parts.append("        ul li:last-child { border-bottom: none; }")
        html_parts.append("        .error { background: linear-gradient(135deg, rgba(255, 107, 107, 0.2) 0%, rgba(255, 107, 107, 0.1) 100%); border: 1px solid #ff6b6b; padding: 20px; border-radius: 10px; margin: 15px 0; }")
        html_parts.append("        .section { margin: 20px 0; }")
        html_parts.append("        /* Custom scrollbar */")
        html_parts.append("        ::-webkit-scrollbar { width: 12px; }")
        html_parts.append("        ::-webkit-scrollbar-track { background: rgba(30, 30, 46, 0.5); border-radius: 6px; }")
        html_parts.append("        ::-webkit-scrollbar-thumb { background: linear-gradient(135deg, #00d4ff 0%, #0099cc 100%); border-radius: 6px; }")
        html_parts.append("        ::-webkit-scrollbar-thumb:hover { background: linear-gradient(135deg, #0099cc 0%, #0077aa 100%); }")
        html_parts.append("    </style>")
        
        # JavaScript
        html_parts.append("    <script>")
        html_parts.append("        function toggleSection(sectionId) {")
        html_parts.append("            var section = document.getElementById(sectionId);")
        html_parts.append("            if (section.style.display === \"none\" || section.style.display === \"\") {")
        html_parts.append("                section.style.display = \"block\";")
        html_parts.append("            } else {")
        html_parts.append("                section.style.display = \"none\";")
        html_parts.append("            }")
        html_parts.append("        }")
        html_parts.append("        function performSearch() {")
        html_parts.append("            var searchTerm = document.getElementById('searchInput').value.toLowerCase();")
        html_parts.append("            var searchInfo = document.getElementById('searchInfo');")
        html_parts.append("            var tables = document.querySelectorAll('table');")
        html_parts.append("            var totalRows = 0;")
        html_parts.append("            var matchingRows = 0;")
        html_parts.append("            document.querySelectorAll('.search-highlight').forEach(function(el) {")
        html_parts.append("                el.classList.remove('search-highlight');")
        html_parts.append("            });")
        html_parts.append("            document.querySelectorAll('.search-hidden').forEach(function(el) {")
        html_parts.append("                el.classList.remove('search-hidden');")
        html_parts.append("            });")
        html_parts.append("            if (searchTerm === '') {")
        html_parts.append("                searchInfo.textContent = 'Enter search term to filter results';")
        html_parts.append("                return;")
        html_parts.append("            }")
        html_parts.append("            tables.forEach(function(table) {")
        html_parts.append("                var rows = table.querySelectorAll('tr');")
        html_parts.append("                rows.forEach(function(row) {")
        html_parts.append("                    totalRows++;")
        html_parts.append("                    var cells = row.querySelectorAll('td, th');")
        html_parts.append("                    var rowText = '';")
        html_parts.append("                    var hasMatch = false;")
        html_parts.append("                    cells.forEach(function(cell) {")
        html_parts.append("                        rowText += cell.textContent + ' ';")
        html_parts.append("                    });")
        html_parts.append("                    if (rowText.toLowerCase().includes(searchTerm)) {")
        html_parts.append("                        hasMatch = true;")
        html_parts.append("                        matchingRows++;")
        html_parts.append("                        cells.forEach(function(cell) {")
        html_parts.append("                            var originalText = cell.innerHTML;")
        html_parts.append("                            var regex = new RegExp('(' + searchTerm + ')', 'gi');")
        html_parts.append("                            cell.innerHTML = originalText.replace(regex, '<span class=\"search-highlight\">$1</span>');")
        html_parts.append("                        });")
        html_parts.append("                    } else {")
        html_parts.append("                        if (row.querySelector('th')) {")
        html_parts.append("                        } else {")
        html_parts.append("                            row.classList.add('search-hidden');")
        html_parts.append("                        }")
        html_parts.append("                    }")
        html_parts.append("                });")
        html_parts.append("            });")
        html_parts.append("            searchInfo.textContent = 'Found ' + matchingRows + ' matching rows';")
        html_parts.append("        }")
        html_parts.append("        function handleKeyPress(event) {")
        html_parts.append("            if (event.key === 'Enter') {")
        html_parts.append("                performSearch();")
        html_parts.append("            }")
        html_parts.append("        }")
        html_parts.append("        function clearSearch() {")
        html_parts.append("            document.getElementById('searchInput').value = '';")
        html_parts.append("            performSearch();")
        html_parts.append("        }")
        html_parts.append("    </script>")
        html_parts.append("</head>")
        
        # Body start
        html_parts.append("<body>")
        
        # Search bar
        html_parts.append("    <div class=\"search-container\">")
        html_parts.append("        <input type=\"text\" id=\"searchInput\" placeholder=\"Search for categories, parameters, filters...\" onkeypress=\"handleKeyPress(event)\">")
        html_parts.append("        <button onclick=\"performSearch()\">Search</button>")
        html_parts.append("        <button onclick=\"clearSearch()\">Clear</button>")
        html_parts.append("        <span class=\"search-info\" id=\"searchInfo\">Enter search term to filter results</span>")
        html_parts.append("    </div>")
        
        # Container start
        html_parts.append("    <div class=\"container\">")
        html_parts.append("        <h1>View Template Comparison Report</h1>")
        html_parts.append("        <div class=\"timestamp\">Generated on: " + timestamp + "</div>")
        html_parts.append("        <div class=\"summary\">")
        html_parts.append("            <h3>Templates Compared:</h3>")
        html_parts.append("            <ul>")
        
        # Template names list
        for template_name in self.template_names:
            try:
                if template_name and str(template_name).strip():
                    html_parts.append("                <li>" + str(template_name).strip() + "</li>")
                else:
                    html_parts.append("                <li>Unknown Template</li>")
            except Exception as e:
                ERROR_HANDLE.print_note("Error processing template name in header: {}".format(str(e)))
                html_parts.append("                <li>Error: Invalid Template Name</li>")
        
        # Close template list and summary
        html_parts.append("            </ul>")
        html_parts.append("        </div>")
        
        return "\n".join(html_parts)
    
    def _generate_comprehensive_comparison_section(self, comparison_data):
        """
        Generate a comprehensive side-by-side comparison of ALL settings.
        
        Args:
            comparison_data: Dictionary containing all template data
            
        Returns:
            str: HTML for comprehensive comparison section
        """
        html_parts = []
        
        html_parts.append("        <div class=\"summary\">")
        html_parts.append("            <h3>Comprehensive Comparison - All Settings</h3>")
        html_parts.append("            <p>Below is a complete side-by-side comparison of all settings across the selected templates:</p>")
        html_parts.append("        </div>")
        
        # Category Overrides Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_categories')\">All Category Overrides (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_categories\" class=\"collapsible\">")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Category</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all categories from all templates
        all_categories = set()
        for template_name, data in comparison_data.items():
            if 'category_overrides' in data:
                all_categories.update(data['category_overrides'].keys())
        
        for category in sorted(all_categories):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + category + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    category_overrides = template_data.get('category_overrides', {})
                    override_data = category_overrides.get(category, None)
                    
                    if override_data is None:
                        html_parts.append("                        <td class=\"same\">Not Set</td>")
                    elif override_data == "UNCONTROLLED":
                        html_parts.append("                        <td style=\"background: linear-gradient(135deg, rgba(255, 165, 2, 0.3) 0%, rgba(255, 165, 2, 0.2) 100%); color: #ffa502; font-weight: bold;\">UNCONTROLLED</td>")
                    else:
                        summary = self._create_override_summary(override_data)
                        html_parts.append("                        <td class=\"different\">" + summary + "</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing category override for {} in {}: {}".format(category, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        # Category Visibility Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_visibility')\">All Category Visibility (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_visibility\" class=\"collapsible\">")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Category</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all categories from all templates
        all_categories = set()
        for template_name, data in comparison_data.items():
            if 'category_visibility' in data:
                all_categories.update(data['category_visibility'].keys())
        
        for category in sorted(all_categories):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + category + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    category_visibility = template_data.get('category_visibility', {})
                    visibility = category_visibility.get(category, 'N/A')
                    
                    if visibility == "UNCONTROLLED":
                        html_parts.append("                        <td style=\"background: linear-gradient(135deg, rgba(255, 165, 2, 0.3) 0%, rgba(255, 165, 2, 0.2) 100%); color: #ffa502; font-weight: bold;\">UNCONTROLLED</td>")
                    elif visibility in ['On', 'Visible']:
                        html_parts.append("                        <td class=\"same\">" + visibility + "</td>")
                    elif visibility == 'Hidden':
                        html_parts.append("                        <td class=\"different\">" + visibility + "</td>")
                    else:
                        html_parts.append("                        <td class=\"different\">" + str(visibility) + "</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing category visibility for {} in {}: {}".format(category, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        # Workset Visibility Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_worksets')\">All Workset Visibility (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_worksets\" class=\"collapsible\">")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Workset</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all worksets from all templates
        all_worksets = set()
        for template_name, data in comparison_data.items():
            if 'workset_visibility' in data:
                all_worksets.update(data['workset_visibility'].keys())
        
        for workset in sorted(all_worksets):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + workset + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    workset_visibility = template_data.get('workset_visibility', {})
                    visibility = workset_visibility.get(workset, 'N/A')
                    
                    if visibility == "UNCONTROLLED":
                        html_parts.append("                        <td style=\"background: linear-gradient(135deg, rgba(255, 165, 2, 0.3) 0%, rgba(255, 165, 2, 0.2) 100%); color: #ffa502; font-weight: bold;\">UNCONTROLLED</td>")
                    elif visibility in ['On', 'Visible']:
                        html_parts.append("                        <td class=\"same\">" + visibility + "</td>")
                    elif visibility == 'Hidden':
                        html_parts.append("                        <td class=\"different\">" + visibility + "</td>")
                    else:
                        html_parts.append("                        <td class=\"different\">" + str(visibility) + "</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing workset visibility for {} in {}: {}".format(workset, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        # View Parameters Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_parameters')\">All View Parameters (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_parameters\" class=\"collapsible\">")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Parameter</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all parameters from all templates
        all_parameters = set()
        for template_name, data in comparison_data.items():
            if 'view_parameters' in data:
                all_parameters.update(data['view_parameters'])
        
        for parameter in sorted(all_parameters):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + parameter + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    view_parameters = template_data.get('view_parameters', [])
                    is_controlled = parameter in view_parameters
                    
                    if is_controlled:
                        html_parts.append("                        <td class=\"same\">Controlled</td>")
                    else:
                        html_parts.append("                        <td class=\"different\">Not Controlled</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing view parameter {} in {}: {}".format(parameter, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        # Uncontrolled Parameters Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_uncontrolled')\" style=\"color: #ff6b6b;\">All Uncontrolled Parameters - DANGEROUS (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_uncontrolled\" class=\"collapsible\">")
        html_parts.append("                <div class=\"warning\">")
        html_parts.append("                    <strong>WARNING:</strong> Uncontrolled parameters are NOT marked as included when the view is used as a template.")
        html_parts.append("                    This can cause inconsistent behavior across views using the same template.")
        html_parts.append("                </div>")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Parameter</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all uncontrolled parameters from all templates
        all_uncontrolled = set()
        for template_name, data in comparison_data.items():
            if 'uncontrolled_parameters' in data:
                all_uncontrolled.update(data['uncontrolled_parameters'])
        
        for parameter in sorted(all_uncontrolled):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + parameter + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    uncontrolled_parameters = template_data.get('uncontrolled_parameters', [])
                    is_uncontrolled = parameter in uncontrolled_parameters
                    
                    if is_uncontrolled:
                        html_parts.append("                        <td style=\"background: linear-gradient(135deg, rgba(255, 107, 107, 0.3) 0%, rgba(255, 107, 107, 0.2) 100%); color: #ff6b6b; font-weight: bold;\">Uncontrolled</td>")
                    else:
                        html_parts.append("                        <td class=\"same\">Controlled</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing uncontrolled parameter {} in {}: {}".format(parameter, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        # Filters Comprehensive Table
        html_parts.append("        <div class=\"section\">")
        html_parts.append("            <h2 class=\"toggle\" onclick=\"toggleSection('comprehensive_filters')\">All Filters (Click to expand)</h2>")
        html_parts.append("            <div id=\"comprehensive_filters\" class=\"collapsible\">")
        html_parts.append("                <table>")
        html_parts.append("                    <tr>")
        html_parts.append("                        <th>Filter</th>")
        
        for template_name in self.template_names:
            html_parts.append("                        <th>" + template_name + "</th>")
        
        html_parts.append("                    </tr>")
        
        # Get all filters from all templates
        all_filters = set()
        for template_name, data in comparison_data.items():
            if 'filters' in data:
                all_filters.update(data['filters'].keys())
        
        for filter_name in sorted(all_filters):
            html_parts.append("                    <tr>")
            html_parts.append("                        <td class=\"template-col\">" + filter_name + "</td>")
            
            for template_name in self.template_names:
                try:
                    template_data = comparison_data.get(template_name, {})
                    filters = template_data.get('filters', {})
                    filter_data = filters.get(filter_name, None)
                    
                    if filter_data is None:
                        html_parts.append("                        <td class=\"same\">Not Applied</td>")
                    elif filter_data == "UNCONTROLLED":
                        html_parts.append("                        <td style=\"background: linear-gradient(135deg, rgba(255, 165, 2, 0.3) 0%, rgba(255, 165, 2, 0.2) 100%); color: #ffa502; font-weight: bold;\">UNCONTROLLED</td>")
                    else:
                        summary = self._create_override_summary(filter_data)
                        html_parts.append("                        <td class=\"different\">" + summary + "</td>")
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing filter {} in {}: {}".format(filter_name, template_name, str(e)))
                    html_parts.append("                        <td class=\"error\">Error</td>")
            
            html_parts.append("                    </tr>")
        
        html_parts.append("                </table>")
        html_parts.append("            </div>")
        html_parts.append("        </div>")
        
        return "\n".join(html_parts)
    
    def _generate_summary_section(self, summary_stats):
        """
        Generate the summary section with statistics.
        
        Args:
            summary_stats: Dictionary containing summary statistics
            
        Returns:
            str: HTML summary section
        """
        # Safely get values with defaults to prevent KeyError
        total_differences = summary_stats.get('total_differences', 0)
        category_overrides = summary_stats.get('category_overrides', 0)
        category_visibility = summary_stats.get('category_visibility', 0)
        workset_visibility = summary_stats.get('workset_visibility', 0)
        view_parameters = summary_stats.get('view_parameters', 0)
        uncontrolled_parameters = summary_stats.get('uncontrolled_parameters', 0)
        filters = summary_stats.get('filters', 0)
        
        # Get detailed category visibility breakdown
        category_visibility_breakdown = summary_stats.get('category_visibility_breakdown', {})
        
        html = """
        <div class="summary">
            <h3>Summary</h3>
            <p><strong>Total differences found:</strong> {}</p>
            <ul>
                <li>Category Overrides: {}</li>
                <li>Category Visibility: {}</li>
                <li>Workset Visibility: {}</li>
                <li>View Parameters: {}</li>
                <li>Uncontrolled Parameters: {} <span style="color: red; font-weight: bold;">DANGEROUS</span></li>
                <li>Filters: {}</li>
            </ul>
        </div>
""".format(total_differences, category_overrides, category_visibility, 
           workset_visibility, view_parameters, uncontrolled_parameters, filters)
        
        # Add detailed category visibility breakdown if available
        if category_visibility_breakdown and isinstance(category_visibility_breakdown, dict):
            html += """
        <div class="summary">
            <h3>Category Visibility Breakdown</h3>
            <table style="width: 100%; margin: 10px 0;">
                <tr>
                    <th>Template</th>
                    <th>On/Visible</th>
                    <th>Hidden</th>
                    <th>Uncontrolled</th>
                    <th>Total Categories</th>
                </tr>
"""
            
            for template_name in self.template_names:
                try:
                    template_data = category_visibility_breakdown.get(template_name, {})
                    on_visible = template_data.get('on_visible', 0)
                    hidden = template_data.get('hidden', 0)
                    uncontrolled = template_data.get('uncontrolled', 0)
                    total = on_visible + hidden + uncontrolled
                    
                    html += """
                <tr>
                    <td><strong>{}</strong></td>
                    <td style="background-color: #d4edda; color: #155724; text-align: center;">{}</td>
                    <td style="background-color: #f8d7da; color: #721c24; text-align: center;">{}</td>
                    <td style="background-color: #fff3cd; color: #856404; text-align: center;">{}</td>
                    <td style="background-color: #e7f3ff; text-align: center;"><strong>{}</strong></td>
                </tr>
""".format(template_name, on_visible, hidden, uncontrolled, total)
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing category visibility breakdown for template {}: {}".format(template_name, str(e)))
                    html += """
                <tr>
                    <td><strong>{}</strong></td>
                    <td colspan="4" style="color: red;">Error processing data</td>
                </tr>
""".format(template_name)
            
            html += """
            </table>
            <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                <strong>Legend:</strong> 
                <span style="background-color: #d4edda; color: #155724; padding: 2px 6px; border-radius: 3px;">On/Visible</span> - Categories that are visible in the view
                <span style="background-color: #f8d7da; color: #721c24; padding: 2px 6px; border-radius: 3px; margin-left: 10px;">Hidden</span> - Categories that are hidden in the view
                <span style="background-color: #fff3cd; color: #856404; padding: 2px 6px; border-radius: 3px; margin-left: 10px;">Uncontrolled</span> - Categories not controlled by the template
            </div>
        </div>
"""
        
        if total_differences == 0:
            html += """
        <div class="summary" style="background-color: #d4edda; border: 1px solid #c3e6cb;">
            <h3>No Differences Found</h3>
            <p>All selected view templates have identical settings.</p>
        </div>
"""
        
        return html
    
    def _generate_detailed_sections(self, differences):
        """
        Generate all detailed comparison sections.
        
        Args:
            differences: Dictionary containing all differences
            
        Returns:
            str: HTML for all detailed sections
        """
        html = ""
        
        try:
            # Safely access differences dictionary with defaults
            category_overrides = differences.get('category_overrides', {})
            category_visibility = differences.get('category_visibility', {})
            workset_visibility = differences.get('workset_visibility', {})
            view_parameters = differences.get('view_parameters', {})
            uncontrolled_parameters = differences.get('uncontrolled_parameters', {})
            filters = differences.get('filters', {})
            
            # Category Overrides Section
            if category_overrides:
                html += self._generate_category_overrides_section(category_overrides)
            
            # Category Visibility Section
            if category_visibility:
                html += self._generate_category_visibility_section(category_visibility)
            
            # Workset Visibility Section
            if workset_visibility:
                html += self._generate_workset_visibility_section(workset_visibility)
            
            # View Parameters Section
            if view_parameters:
                html += self._generate_view_parameters_section(view_parameters)
            
            # Uncontrolled Parameters Section (DANGEROUS)
            if uncontrolled_parameters:
                html += self._generate_uncontrolled_parameters_section(uncontrolled_parameters)
            
            # Filters Section
            if filters:
                html += self._generate_filters_section(filters)
                
        except Exception as e:
            # Add error section if detailed sections generation fails
            html += """
        <div class="section">
            <h2 style="color: red;">Error Generating Detailed Sections</h2>
            <div class="error">
                <p>An error occurred while generating detailed comparison sections:</p>
                <p><strong>{}</strong></p>
            </div>
        </div>
""".format(str(e))
        
        return html
    
    def _generate_category_overrides_section(self, differences):
        """
        Generate the category overrides comparison section.
        
        Args:
            differences: Dictionary of category override differences
            
        Returns:
            str: HTML for category overrides section
        """
        try:
            html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('category_overrides')">Category Overrides (Click to expand)</h2>
            <div id="category_overrides" class="collapsible">
                <table>
                    <tr>
                        <th>Category</th>
"""
            
            for template_name in self.template_names:
                html += "                        <th>{}</th>\n".format(template_name)
            
            html += "                    </tr>\n"
            
            for category, values in differences.items():
                html += "                    <tr><td class='template-col'>{}</td>".format(category)
                for template_name in self.template_names:
                    value = values.get(template_name, 'N/A')
                    if value == "UNCONTROLLED":
                        html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                    elif value:
                        summary = self._create_override_summary(value)
                        html += "<td class='different'>{}</td>".format(summary)
                    else:
                        html += "<td class='same'>Not Set</td>"
                html += "</tr>\n"
            
            html += "                </table></div></div>\n"
            return html
            
        except Exception as e:
            # Return error section if generation fails
            return """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('category_overrides')">Category Overrides (Click to expand)</h2>
            <div id="category_overrides" class="collapsible">
                <div class="error">
                    <p>Error generating category overrides section: {}</p>
                </div>
            </div>
        </div>
""".format(str(e))
    
    def _create_override_summary(self, override_data):
        """
        Create a summary string for override data.
        
        Args:
            override_data: Dictionary containing override details
            
        Returns:
            str: Summary string
        """
        try:
            if not isinstance(override_data, dict):
                return "Invalid Data"
                
            summary_parts = []
            
            if override_data.get('halftone'):
                summary_parts.append("Halftone")
            
            if override_data.get('line_weight') != -1:
                summary_parts.append("LineWeight: {}".format(override_data['line_weight']))
            
            if override_data.get('line_color') != "Default":
                summary_parts.append("LineColor: {}".format(override_data['line_color']))
            
            if override_data.get('line_pattern') != "Default":
                summary_parts.append("LinePattern: {}".format(override_data['line_pattern']))
            
            if override_data.get('cut_line_weight') != -1:
                summary_parts.append("CutLineWeight: {}".format(override_data['cut_line_weight']))
            
            if override_data.get('cut_line_color') != "Default":
                summary_parts.append("CutLineColor: {}".format(override_data['cut_line_color']))
            
            if override_data.get('cut_line_pattern') != "Default":
                summary_parts.append("CutLinePattern: {}".format(override_data['cut_line_pattern']))
            
            if override_data.get('cut_fill_pattern') != "Default":
                summary_parts.append("CutFillPattern: {}".format(override_data['cut_fill_pattern']))
            
            if override_data.get('cut_fill_color') != "Default":
                summary_parts.append("CutFillColor: {}".format(override_data['cut_fill_color']))
            
            if override_data.get('projection_fill_pattern') != "Default":
                summary_parts.append("ProjectionFillPattern: {}".format(override_data['projection_fill_pattern']))
            
            if override_data.get('projection_fill_color') != "Default":
                summary_parts.append("ProjectionFillColor: {}".format(override_data['projection_fill_color']))
            
            if override_data.get('transparency') != 0:
                summary_parts.append("Transparency: {}".format(override_data['transparency']))
            
            return " | ".join(summary_parts) if summary_parts else "Default"
            
        except Exception as e:
            return "Error: {}".format(str(e))
    
    def _generate_category_visibility_section(self, differences):
        """
        Generate the category visibility comparison section.
        
        Args:
            differences: Dictionary of category visibility differences
            
        Returns:
            str: HTML for category visibility section
        """
        return self._generate_simple_comparison_section('category_visibility', 'Category Visibility', differences)
    
    def _generate_workset_visibility_section(self, differences):
        """
        Generate the workset visibility comparison section.
        
        Args:
            differences: Dictionary of workset visibility differences
            
        Returns:
            str: HTML for workset visibility section
        """
        return self._generate_simple_comparison_section('workset_visibility', 'Workset Visibility', differences)
    
    def _generate_view_parameters_section(self, differences):
        """
        Generate the view parameters comparison section.
        
        Args:
            differences: Dictionary of view parameter differences
            
        Returns:
            str: HTML for view parameters section
        """
        return self._generate_boolean_comparison_section('view_parameters', 'View Parameters', differences, 'Controlled', 'Not Controlled')
    
    def _generate_uncontrolled_parameters_section(self, differences):
        """
        Generate the uncontrolled parameters section (DANGEROUS).
        
        Args:
            differences: Dictionary of uncontrolled parameter differences
            
        Returns:
            str: HTML for uncontrolled parameters section
        """
        html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('uncontrolled_parameters')" style="color: red;">Uncontrolled Parameters - DANGEROUS (Click to expand)</h2>
            <div id="uncontrolled_parameters" class="collapsible">
                <div style="background-color: #ffe6e6; border: 2px solid #ff0000; padding: 10px; margin-bottom: 15px; border-radius: 5px;">
                    <strong>WARNING:</strong> Uncontrolled parameters are NOT marked as included when the view is used as a template. 
                    This can cause inconsistent behavior across views using the same template. 
                    These parameters should be reviewed and controlled if needed for consistency.
                </div>
                <table>
                    <tr>
                        <th>Parameter</th>
"""
        
        for template_name in self.template_names:
            html += "                        <th>{}</th>\n".format(template_name)
        
        html += "                    </tr>\n"
        
        for param, values in differences.items():
            html += "                    <tr><td class='template-col'>{}</td>".format(param)
            for template_name in self.template_names:
                value = values.get(template_name, False)
                if value == "UNCONTROLLED":
                    html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                elif value:
                    html += "<td class='different' style='background-color: #ffcccc;'>Uncontrolled</td>"
                else:
                    html += "<td class='same'>Controlled</td>"
            html += "</tr>\n"
        
        html += "                </table></div></div>\n"
        return html
    
    def _generate_filters_section(self, differences):
        """
        Generate the filters comparison section.
        
        Args:
            differences: Dictionary of filter differences
            
        Returns:
            str: HTML for filters section
        """
        html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('filters')">Filters (Click to expand)</h2>
            <div id="filters" class="collapsible">
                <table>
                    <tr>
                        <th>Filter</th>
"""
        
        for template_name in self.template_names:
            html += "                        <th>{}</th>\n".format(template_name)
        
        html += "                    </tr>\n"
        
        for filter_name, values in differences.items():
            html += "                    <tr><td class='template-col'>{}</td>".format(filter_name)
            for template_name in self.template_names:
                value = values.get(template_name, 'N/A')
                if value == "UNCONTROLLED":
                    html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                elif value:
                    summary = self._create_override_summary(value)
                    html += "<td class='different'>{}</td>".format(summary)
                else:
                    html += "<td class='same'>Not Applied</td>"
            html += "</tr>\n"
        
        html += "                </table></div></div>\n"
        return html
    
    def _generate_simple_comparison_section(self, section_id, section_title, differences):
        """
        Generate a simple comparison section for basic values.
        
        Args:
            section_id: ID for the HTML section
            section_title: Title for the section
            differences: Dictionary of differences
            
        Returns:
            str: HTML for the section
        """
        try:
            # Ensure template_names is a valid list
            if not isinstance(self.template_names, list):
                self.template_names = []
            
            html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <table>
                    <tr>
                        <th>Item</th>
""".format(section_id, section_title, section_id)
            
            for template_name in self.template_names:
                try:
                    if template_name:
                        html += "                        <th>{}</th>\n".format(str(template_name))
                    else:
                        html += "                        <th>Unknown</th>\n"
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing template name in simple comparison: {}".format(str(e)))
                    html += "                        <th>Error</th>\n"
            
            html += "                    </tr>\n"
            
            for item, values in differences.items():
                try:
                    html += "                    <tr><td class='template-col'>{}</td>".format(str(item))
                    for template_name in self.template_names:
                        try:
                            value = values.get(template_name, 'N/A')
                            if value == "UNCONTROLLED":
                                html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                            elif value in ["On", "Visible", "Hidden"]:
                                html += "<td class='same'>{}</td>".format(str(value))
                            else:
                                html += "<td class='different'>{}</td>".format(str(value))
                        except Exception as e:
                            ERROR_HANDLE.print_note("Error processing value for template {}: {}".format(template_name, str(e)))
                            html += "<td class='different'>Error</td>"
                    html += "</tr>\n"
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing item {}: {}".format(item, str(e)))
                    continue
            
            html += "                </table></div></div>\n"
            return html
            
        except Exception as e:
            ERROR_HANDLE.print_note("Error generating simple comparison section: {}".format(str(e)))
            return """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <div class="error">
                    <p>Error generating {} section: {}</p>
                </div>
            </div>
        </div>
""".format(section_id, section_title, section_id, section_title, str(e))
    
    def _generate_boolean_comparison_section(self, section_id, section_title, differences, true_text, false_text):
        """
        Generate a boolean comparison section.
        
        Args:
            section_id: ID for the HTML section
            section_title: Title for the section
            differences: Dictionary of differences
            true_text: Text to display for True values
            false_text: Text to display for False values
            
        Returns:
            str: HTML for the section
        """
        try:
            # Ensure template_names is a valid list
            if not isinstance(self.template_names, list):
                self.template_names = []
            
            html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <table>
                    <tr>
                        <th>Parameter</th>
""".format(section_id, section_title, section_id)
            
            for template_name in self.template_names:
                try:
                    if template_name:
                        html += "                        <th>{}</th>\n".format(str(template_name))
                    else:
                        html += "                        <th>Unknown</th>\n"
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing template name in boolean comparison: {}".format(str(e)))
                    html += "                        <th>Error</th>\n"
            
            html += "                    </tr>\n"
            
            for item, values in differences.items():
                try:
                    html += "                    <tr><td class='template-col'>{}</td>".format(str(item))
                    for template_name in self.template_names:
                        try:
                            value = values.get(template_name, False)
                            if value == "UNCONTROLLED":
                                html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                            elif value:
                                html += "<td class='same'>{}</td>".format(str(true_text))
                            else:
                                html += "<td class='different'>{}</td>".format(str(false_text))
                        except Exception as e:
                            ERROR_HANDLE.print_note("Error processing boolean value for template {}: {}".format(template_name, str(e)))
                            html += "<td class='different'>Error</td>"
                    html += "</tr>\n"
                except Exception as e:
                    ERROR_HANDLE.print_note("Error processing boolean item {}: {}".format(item, str(e)))
                    continue
            
            html += "                </table></div></div>\n"
            return html
            
        except Exception as e:
            ERROR_HANDLE.print_note("Error generating boolean comparison section: {}".format(str(e)))
            return """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <div class="error">
                    <p>Error generating {} section: {}</p>
                </div>
            </div>
        </div>
""".format(section_id, section_title, section_id, section_title, str(e))
    
    def _generate_html_footer(self):
        """
        Generate the HTML footer.
        
        Returns:
            str: HTML footer
        """
        return """
    </div>
</body>
</html>
"""
    
    def save_report_to_file(self, html_content):
        """
        Save the HTML report to a temporary file and return the filepath.
        
        Args:
            html_content: The HTML content to save
            
        Returns:
            str: Filepath of the saved HTML file
        """
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "ViewTemplate_Comparison_{}.html".format(timestamp)
        filepath = os.path.join(temp_dir, filename)
        
        # Write HTML content to file (IronPython compatible)
        with open(filepath, 'w') as f:
            f.write(html_content)
        
        return filepath 


if __name__ == "__main__":
    pass