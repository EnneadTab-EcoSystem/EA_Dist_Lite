"""
HTML Report Generator Module

This module handles the generation of interactive HTML reports for view template comparisons,
including styling, JavaScript functionality, and organized data presentation.
"""

import os
import tempfile
from datetime import datetime


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
    
    def generate_comparison_report(self, differences, summary_stats):
        """
        Generate the complete HTML comparison report.
        
        Args:
            differences: Dictionary containing all differences found
            summary_stats: Dictionary containing summary statistics
            
        Returns:
            str: Complete HTML report as string
        """
        html = self._generate_html_header()
        html += self._generate_summary_section(summary_stats)
        html += self._generate_detailed_sections(differences)
        html += self._generate_html_footer()
        
        return html
    
    def _generate_html_header(self):
        """
        Generate the HTML header with CSS and JavaScript.
        
        Returns:
            str: HTML header section
        """
        return """
<!DOCTYPE html>
<html>
<head>
    <title>View Template Comparison Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; border-bottom: 3px solid #007acc; padding-bottom: 10px; }
        h2 { color: #007acc; cursor: pointer; padding: 10px; background-color: #f0f8ff; border-radius: 5px; margin: 10px 0; }
        h2:hover { background-color: #e0f0ff; }
        .collapsible { display: none; padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin: 5px 0; }
        table { width: 100%; border-collapse: collapse; margin: 10px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #007acc; color: white; font-weight: bold; }
        .template-col { background-color: #f8f9fa; font-weight: bold; }
        .same { background-color: #d4edda; color: #155724; }
        .different { background-color: #fff3cd; color: #856404; }
        .summary { background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 15px 0; }
        .warning { background-color: #ffe6e6; border: 2px solid #ff0000; padding: 10px; margin-bottom: 15px; border-radius: 5px; }
        .timestamp { color: #666; font-size: 0.9em; text-align: center; margin: 10px 0; }
    </style>
    <script>
        function toggleSection(sectionId) {
            var section = document.getElementById(sectionId);
            if (section.style.display === "none" || section.style.display === "") {
                section.style.display = "block";
            } else {
                section.style.display = "none";
            }
        }
    </script>
</head>
<body>
    <div class="container">
        <h1>View Template Comparison Report</h1>
        <div class="timestamp">Generated on: {}</div>
        <div class="summary">
            <h3>Templates Compared:</h3>
            <ul>
""".format(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        
        for template_name in self.template_names:
            html += "                <li>{}</li>\n".format(template_name)
        
        html += """            </ul>
        </div>
"""
        
        return html
    
    def _generate_summary_section(self, summary_stats):
        """
        Generate the summary section with statistics.
        
        Args:
            summary_stats: Dictionary containing summary statistics
            
        Returns:
            str: HTML summary section
        """
        total_differences = summary_stats['total_differences']
        
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
""".format(total_differences, summary_stats['category_overrides'], summary_stats['category_visibility'], 
           summary_stats['workset_visibility'], summary_stats['view_parameters'], 
           summary_stats['uncontrolled_parameters'], summary_stats['filters'])
        
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
        
        # Category Overrides Section
        if differences['category_overrides']:
            html += self._generate_category_overrides_section(differences['category_overrides'])
        
        # Category Visibility Section
        if differences['category_visibility']:
            html += self._generate_category_visibility_section(differences['category_visibility'])
        
        # Workset Visibility Section
        if differences['workset_visibility']:
            html += self._generate_workset_visibility_section(differences['workset_visibility'])
        
        # View Parameters Section
        if differences['view_parameters']:
            html += self._generate_view_parameters_section(differences['view_parameters'])
        
        # Uncontrolled Parameters Section (DANGEROUS)
        if differences['uncontrolled_parameters']:
            html += self._generate_uncontrolled_parameters_section(differences['uncontrolled_parameters'])
        
        # Filters Section
        if differences['filters']:
            html += self._generate_filters_section(differences['filters'])
        
        return html
    
    def _generate_category_overrides_section(self, differences):
        """
        Generate the category overrides comparison section.
        
        Args:
            differences: Dictionary of category override differences
            
        Returns:
            str: HTML for category overrides section
        """
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
    
    def _create_override_summary(self, override_data):
        """
        Create a summary string for override data.
        
        Args:
            override_data: Dictionary containing override details
            
        Returns:
            str: Summary string
        """
        summary_parts = []
        
        if override_data.get('halftone'):
            summary_parts.append("Halftone")
        
        if override_data.get('line_weight') != -1:
            summary_parts.append("LW:{}".format(override_data['line_weight']))
        
        if override_data.get('line_color') != "Default":
            summary_parts.append("LC:{}".format(override_data['line_color']))
        
        if override_data.get('line_pattern') != "Default":
            summary_parts.append("LP:{}".format(override_data['line_pattern']))
        
        if override_data.get('cut_line_weight') != -1:
            summary_parts.append("CLW:{}".format(override_data['cut_line_weight']))
        
        if override_data.get('cut_line_color') != "Default":
            summary_parts.append("CLC:{}".format(override_data['cut_line_color']))
        
        if override_data.get('cut_line_pattern') != "Default":
            summary_parts.append("CLP:{}".format(override_data['cut_line_pattern']))
        
        if override_data.get('cut_fill_pattern') != "Default":
            summary_parts.append("CFP:{}".format(override_data['cut_fill_pattern']))
        
        if override_data.get('cut_fill_color') != "Default":
            summary_parts.append("CFC:{}".format(override_data['cut_fill_color']))
        
        if override_data.get('projection_fill_pattern') != "Default":
            summary_parts.append("PFP:{}".format(override_data['projection_fill_pattern']))
        
        if override_data.get('projection_fill_color') != "Default":
            summary_parts.append("PFC:{}".format(override_data['projection_fill_color']))
        
        if override_data.get('transparency') != 0:
            summary_parts.append("T:{}".format(override_data['transparency']))
        
        return " | ".join(summary_parts) if summary_parts else "Default"
    
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
        html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <table>
                    <tr>
                        <th>Item</th>
""".format(section_id, section_title, section_id)
        
        for template_name in self.template_names:
            html += "                        <th>{}</th>\n".format(template_name)
        
        html += "                    </tr>\n"
        
        for item, values in differences.items():
            html += "                    <tr><td class='template-col'>{}</td>".format(item)
            for template_name in self.template_names:
                value = values.get(template_name, 'N/A')
                if value == "UNCONTROLLED":
                    html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                elif value in ["On", "Visible", "Hidden"]:
                    html += "<td class='same'>{}</td>".format(value)
                else:
                    html += "<td class='different'>{}</td>".format(value)
            html += "</tr>\n"
        
        html += "                </table></div></div>\n"
        return html
    
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
        html = """
        <div class="section">
            <h2 class="toggle" onclick="toggleSection('{}')">{}</h2>
            <div id="{}" class="collapsible">
                <table>
                    <tr>
                        <th>Parameter</th>
""".format(section_id, section_title, section_id)
        
        for template_name in self.template_names:
            html += "                        <th>{}</th>\n".format(template_name)
        
        html += "                    </tr>\n"
        
        for item, values in differences.items():
            html += "                    <tr><td class='template-col'>{}</td>".format(item)
            for template_name in self.template_names:
                value = values.get(template_name, False)
                if value == "UNCONTROLLED":
                    html += "<td style='background-color: #FF8C00; color: white; font-weight: bold;'>UNCONTROLLED</td>"
                elif value:
                    html += "<td class='same'>{}</td>".format(true_text)
                else:
                    html += "<td class='different'>{}</td>".format(false_text)
            html += "</tr>\n"
        
        html += "                </table></div></div>\n"
        return html
    
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
        
        # Write HTML content to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath 
    


if __name__ == "__main__":
    pass