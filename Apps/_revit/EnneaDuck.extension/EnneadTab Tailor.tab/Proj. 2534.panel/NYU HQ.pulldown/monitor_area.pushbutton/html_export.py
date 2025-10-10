#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
HTML Export Module - Handles area matching and HTML report generation
Uses exact matching on 3 parameters: Department, Program Type, Program Type Detail
"""

import os
import webbrowser
from datetime import datetime
import config


class AreaMatcher:
    """Exact matching between Excel requirements and Revit areas using 3 parameters"""
    
    def match_areas_to_requirements(self, excel_data, revit_data):
        """
        Match Revit areas to Excel requirements
        
        Args:
            excel_data: Dictionary of Excel data with RowData objects
            revit_data: Dictionary with scheme names as keys and list of area objects as values
                {
                    'scheme1': [area_object1, area_object2, ...],
                    'scheme2': [area_object1, area_object2, ...]
                }
            
        Returns:
            dict: Dictionary with scheme names as keys and match data as values
        """
        all_matches = {}
        
        for scheme_name, areas_list in revit_data.items():
            if isinstance(areas_list, list):
                matches = self._match_single_scheme(excel_data, areas_list)
                
                # Calculate scheme info
                total_sf = sum(area['area_sf'] for area in areas_list)
                scheme_info = {
                    'name': scheme_name,
                    'count': len(areas_list),
                    'total_sf': total_sf
                }
                
                all_matches[scheme_name] = {
                    'matches': matches,
                    'scheme_info': scheme_info
                }
        
        return all_matches
    
    def _match_single_scheme(self, excel_data, areas_list):
        """
        Match areas for a single scheme
        
        Args:
            excel_data: Dictionary of Excel data with RowData objects
            areas_list: List of area objects
            
        Returns:
            list: List of match results
        """
        matches = []
        
        for room_key, requirement in excel_data.items():
            # Extract requirement data from RowData object using Excel column names
            room_name = getattr(requirement, config.PROGRAM_TYPE_DETAIL_KEY[config.APP_EXCEL], room_key)
            department = getattr(requirement, config.DEPARTMENT_KEY[config.APP_EXCEL], '')
            program_type = getattr(requirement, config.PROGRAM_TYPE_KEY[config.APP_EXCEL], '')
            target_count = getattr(requirement, config.COUNT_KEY[config.APP_EXCEL], 0)
            target_dgsf = getattr(requirement, config.SCALED_DGSF_KEY[config.APP_EXCEL], 0)
            
            # Find matching Revit areas using exact 3-parameter match
            matching_areas = self._find_matching_areas(
                room_name,  # program_type_detail
                department, 
                program_type, 
                areas_list
            )
            
            # Calculate actual counts and areas
            actual_count = len(matching_areas)
            actual_dgsf = sum(area['area_sf'] for area in matching_areas)
            
            # Calculate deltas
            count_delta = actual_count - target_count
            dgsf_delta = actual_dgsf - target_dgsf
            dgsf_percentage = (dgsf_delta / target_dgsf * 100) if target_dgsf > 0 else 0
            
            # Determine status
            status = self._determine_status(
                target_count, 
                target_dgsf, 
                actual_count, 
                actual_dgsf
            )
            
            match_result = {
                'room_name': room_name,
                'department': department,
                'division': program_type,
                'target_count': target_count,
                'target_dgsf': target_dgsf,
                'actual_count': actual_count,
                'actual_dgsf': actual_dgsf,
                'count_delta': count_delta,
                'dgsf_delta': dgsf_delta,
                'dgsf_percentage': dgsf_percentage,
                'status': status,
                'matching_areas': matching_areas,
                'match_quality': self._calculate_match_quality_simple(matching_areas)
            }
            
            matches.append(match_result)
        
        return matches
    
    def _find_matching_areas(self, req_detail, req_dept, req_type, areas_list):
        """
        Find Revit areas that EXACTLY match the requirement using 3 parameters
        
        Args:
            req_detail: Requirement program type detail
            req_dept: Requirement department
            req_type: Requirement program type
            areas_list: List of area objects
            
        Returns:
            list: List of matching area objects (exact match only)
        """
        matching_areas = []
        
        for area_object in areas_list:
            # Get the 3 parameters from area object (using dict keys, not config params)
            area_dept = area_object.get('department', '')
            area_type = area_object.get('program_type', '')
            area_detail = area_object.get('program_type_detail', '')
            
            # EXACT match on all 3 parameters (case-insensitive, whitespace-trimmed)
            if (req_detail.lower().strip() == area_detail.lower().strip() and 
                req_dept.lower().strip() == area_dept.lower().strip() and 
                req_type.lower().strip() == area_type.lower().strip()):
                matching_areas.append(area_object)
        
        return matching_areas
    
    def _determine_status(self, target_count, target_dgsf, actual_count, actual_dgsf):
        """Determine fulfillment status"""
        count_met = actual_count >= target_count
        area_met = actual_dgsf >= target_dgsf * (1 - config.AREA_TOLERANCE_PERCENTAGE / 100)
        
        if count_met and area_met:
            return "Fulfilled"
        elif actual_count > 0 and actual_dgsf > 0:
            return "Partial"
        else:
            return "Missing"
    
    def _calculate_match_quality_simple(self, matching_areas):
        """Calculate overall match quality based on number of matches"""
        if not matching_areas:
            return "No Match"
        elif len(matching_areas) == 1:
            return "High"
        elif len(matching_areas) <= 3:
            return "Medium"
        else:
            return "Low"
    
    def get_unmatched_areas(self, excel_data, areas_list):
        """
        Get Revit areas that don't match any Excel requirements
        
        Args:
            excel_data: Dictionary of Excel data with RowData objects
            areas_list: List of area objects
            
        Returns:
            list: List of unmatched area objects
        """
        # Get all matched area objects
        all_matched_areas = []
        
        for room_key, requirement in excel_data.items():
            room_name = getattr(requirement, config.PROGRAM_TYPE_DETAIL_KEY[config.APP_EXCEL], room_key)
            department = getattr(requirement, config.DEPARTMENT_KEY[config.APP_EXCEL], '')
            program_type = getattr(requirement, config.PROGRAM_TYPE_KEY[config.APP_EXCEL], '')
            
            matching_areas = self._find_matching_areas(
                room_name,  # program_type_detail
                department, 
                program_type, 
                areas_list
            )
            all_matched_areas.extend(matching_areas)
        
        # Find unmatched areas by comparing object references
        matched_ids = set(id(area) for area in all_matched_areas)
        unmatched = [area for area in areas_list if id(area) not in matched_ids]
        
        return unmatched


class HTMLReportGenerator:
    """Generate HTML reports for area comparison"""
    
    def __init__(self):
        self.reports_dir = os.path.join(os.path.dirname(__file__), config.REPORTS_DIR)
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
    
    def generate_html_report(self, excel_data, revit_data):
        """
        Generate the complete HTML report
        
        Args:
            excel_data: Dictionary of Excel data with RowData objects
            revit_data: Dictionary of area data (single scheme or multiple schemes)
            
        Returns:
            tuple: (filepath, all_matches, all_unmatched_areas)
        """
        # Match areas to requirements
        matcher = AreaMatcher()
        all_matches = matcher.match_areas_to_requirements(excel_data, revit_data)
        
        # Get unmatched areas for each scheme
        all_unmatched_areas = {}
        for scheme_name, areas_list in revit_data.items():
            if isinstance(areas_list, list):
                unmatched = matcher.get_unmatched_areas(excel_data, areas_list)
                all_unmatched_areas[scheme_name] = unmatched
        
        # Generate HTML content
        html_content = self._create_html_content(all_matches, all_unmatched_areas)
        
        # Save to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = "area_report_{}.html".format(timestamp)
        filepath = os.path.join(self.reports_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Also save as latest_report.html for easy access
        latest_path = os.path.join(self.reports_dir, config.LATEST_REPORT_FILENAME)
        with open(latest_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return filepath, all_matches, all_unmatched_areas
    
    def _create_html_content(self, all_matches, all_unmatched_areas):
        """Create the HTML content for the report"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Check if we have multiple schemes or single scheme
        if isinstance(all_matches, dict) and any(isinstance(value, dict) for value in all_matches.values()):
            # Multiple schemes
            return self._create_multiple_scheme_html(all_matches, all_unmatched_areas, current_time)
        else:
            # Single scheme (fallback)
            return self._create_single_scheme_html(all_matches, all_unmatched_areas, current_time)
    
    def _create_single_scheme_html(self, matches, unmatched_areas, current_time):
        """Create HTML for single scheme"""
        # Calculate summary statistics
        total_target_count = sum(match['target_count'] for match in matches)
        total_actual_count = sum(match['actual_count'] for match in matches)
        total_target_dgsf = sum(match['target_dgsf'] for match in matches)
        total_actual_dgsf = sum(match['actual_dgsf'] for match in matches)
        
        fulfilled_count = sum(1 for match in matches if match['status'] == 'Fulfilled')
        partial_count = sum(1 for match in matches if match['status'] == 'Partial')
        missing_count = sum(1 for match in matches if match['status'] == 'Missing')
        
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        {css_styles}
    </style>
</head>
<body>
    <div class="container">
        <header class="report-header">
            <h1>🏥 {report_title}</h1>
            <div class="report-info">
                <p><strong>Generated:</strong> {current_time}</p>
                <p><strong>Project:</strong> {project_name}</p>
            </div>
        </header>
        
        <div class="summary-section">
            <h2>📊 Summary</h2>
            <div class="summary-cards">
                <div class="card">
                    <h3>Total Requirements</h3>
                    <div class="card-value">{total_reqs}</div>
                    <div class="card-label">Room Types</div>
                </div>
                <div class="card">
                    <h3>Target Count</h3>
                    <div class="card-value">{target_count}</div>
                    <div class="card-label">Areas Required</div>
                </div>
                <div class="card">
                    <h3>Actual Count</h3>
                    <div class="card-value">{actual_count}</div>
                    <div class="card-label">Areas Found</div>
                </div>
                <div class="card">
                    <h3>Target DGSF</h3>
                    <div class="card-value">{target_dgsf}</div>
                    <div class="card-label">Square Feet</div>
                </div>
                <div class="card">
                    <h3>Actual DGSF</h3>
                    <div class="card-value">{actual_dgsf}</div>
                    <div class="card-label">Square Feet</div>
                </div>
                <div class="card">
                    <h3>Compliance</h3>
                    <div class="card-value">{fulfilled_count}/{total_reqs}</div>
                    <div class="card-label">Fulfilled</div>
                </div>
            </div>
        </div>
        
        <div class="status-summary">
            <h2>📈 Status Breakdown</h2>
            <div class="status-cards">
                <div class="status-card fulfilled">
                    <h3>✅ Fulfilled</h3>
                    <div class="status-count">{fulfilled_count}</div>
                </div>
                <div class="status-card partial">
                    <h3>⚠️ Partial</h3>
                    <div class="status-count">{partial_count}</div>
                </div>
                <div class="status-card missing">
                    <h3>❌ Missing</h3>
                    <div class="status-count">{missing_count}</div>
                </div>
            </div>
        </div>
        
        <div class="comparison-section">
            <h2>📋 Detailed Comparison</h2>
            <div class="table-container">
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>{col_area_detail}</th>
                            <th>{col_department}</th>
                            <th>{col_program_type}</th>
                            <th>{col_target_count}</th>
                            <th>{col_target_dgsf}</th>
                            <th>{col_actual_count}</th>
                            <th>{col_actual_dgsf}</th>
                            <th>{col_count_delta}</th>
                            <th>{col_dgsf_delta}</th>
                            <th>{col_dgsf_percentage}</th>
                            <th>{col_status}</th>
                            <th>{col_match_quality}</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
        
        {unmatched_section}
        
        <footer class="report-footer">
            <p>Report generated by Monitor Area System | {current_time}</p>
        </footer>
    </div>
    
    <script>
        {javascript}
    </script>
</body>
</html>
""".format(
            report_title=config.REPORT_TITLE,
            css_styles=self._get_css_styles(),
            current_time=current_time,
            project_name=config.PROJECT_NAME,
            total_reqs=len(matches),
            target_count="{:,}".format(total_target_count),
            actual_count="{:,}".format(total_actual_count),
            target_dgsf="{:,.0f}".format(total_target_dgsf),
            actual_dgsf="{:,.0f}".format(total_actual_dgsf),
            fulfilled_count=fulfilled_count,
            partial_count=partial_count,
            missing_count=missing_count,
            col_area_detail=config.TABLE_COLUMN_HEADERS['area_detail'],
            col_department=config.TABLE_COLUMN_HEADERS['department'],
            col_program_type=config.TABLE_COLUMN_HEADERS['program_type'],
            col_target_count=config.TABLE_COLUMN_HEADERS['target_count'],
            col_target_dgsf=config.TABLE_COLUMN_HEADERS['target_dgsf'],
            col_actual_count=config.TABLE_COLUMN_HEADERS['actual_count'],
            col_actual_dgsf=config.TABLE_COLUMN_HEADERS['actual_dgsf'],
            col_count_delta=config.TABLE_COLUMN_HEADERS['count_delta'],
            col_dgsf_delta=config.TABLE_COLUMN_HEADERS['dgsf_delta'],
            col_dgsf_percentage=config.TABLE_COLUMN_HEADERS['dgsf_percentage'],
            col_status=config.TABLE_COLUMN_HEADERS['status'],
            col_match_quality=config.TABLE_COLUMN_HEADERS['match_quality'],
            table_rows=self._create_table_rows(matches),
            unmatched_section=self._create_unmatched_section(unmatched_areas),
            javascript=self._get_javascript()
        )
        return html
    
    def _create_multiple_scheme_html(self, all_matches, all_unmatched_areas, current_time):
        """Create HTML for multiple schemes"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
        {css_styles}
    </style>
</head>
<body>
    <div class="container">
        <header class="report-header">
            <h1>🏥 {report_title}</h1>
            <div class="report-info">
                <p><strong>Generated:</strong> {current_time}</p>
                <p><strong>Project:</strong> {project_name}</p>
                <p><strong>Area Schemes:</strong> {scheme_count} schemes compared</p>
            </div>
        </header>
        
        <div class="scheme-summary">
            <h2>📊 Area Scheme Summary</h2>
            <div class="scheme-cards">
        """.format(
            report_title=config.REPORT_TITLE,
            css_styles=self._get_css_styles(),
            current_time=current_time,
            project_name=config.PROJECT_NAME,
            scheme_count=len(all_matches)
        )
        
        # Add scheme summary cards
        for scheme_name, scheme_data in all_matches.items():
            matches = scheme_data.get('matches', [])
            scheme_info = scheme_data.get('scheme_info', {})
            
            fulfilled_count = sum(1 for match in matches if match['status'] == 'Fulfilled')
            total_count = len(matches)
            
            html += """
                <div class="scheme-card">
                    <h3>{scheme_name}</h3>
                    <div class="scheme-stats">
                        <div class="stat">
                            <span class="stat-value">{total_count}</span>
                            <span class="stat-label">Requirements</span>
                        </div>
                        <div class="stat">
                            <span class="stat-value">{fulfilled_count}</span>
                            <span class="stat-label">Fulfilled</span>
                        </div>
                        <div class="stat">
                            <span class="stat-value">{area_count}</span>
                            <span class="stat-label">Areas</span>
                        </div>
                        <div class="stat">
                            <span class="stat-value">{total_sf}</span>
                            <span class="stat-label">Total SF</span>
                        </div>
                    </div>
                </div>
            """.format(
                scheme_name=scheme_name,
                total_count=total_count,
                fulfilled_count=fulfilled_count,
                area_count=scheme_info.get('count', 0),
                total_sf="{:,.0f}".format(scheme_info.get('total_sf', 0))
            )
        
        html += """
            </div>
        </div>
        
        <div class="scheme-comparisons">
        """
        
        # Add detailed comparison for each scheme
        for scheme_name, scheme_data in all_matches.items():
            matches = scheme_data.get('matches', [])
            unmatched_areas = all_unmatched_areas.get(scheme_name, {})
            
            html += """
            <div class="scheme-section">
                <h2>📋 {scheme_name} - Detailed Comparison</h2>
                <div class="table-container">
                    <table class="comparison-table">
                        <thead>
                            <tr>
                                <th>{col_area_detail}</th>
                                <th>{col_department}</th>
                                <th>{col_program_type}</th>
                                <th>{col_target_count}</th>
                                <th>{col_target_dgsf}</th>
                                <th>{col_actual_count}</th>
                                <th>{col_actual_dgsf}</th>
                                <th>{col_count_delta}</th>
                                <th>{col_dgsf_delta}</th>
                                <th>{col_dgsf_percentage}</th>
                                <th>{col_status}</th>
                                <th>{col_match_quality}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {table_rows}
                        </tbody>
                    </table>
                </div>
                
                {unmatched_section}
            </div>
            """.format(
                scheme_name=scheme_name,
                col_area_detail=config.TABLE_COLUMN_HEADERS['area_detail'],
                col_department=config.TABLE_COLUMN_HEADERS['department'],
                col_program_type=config.TABLE_COLUMN_HEADERS['program_type'],
                col_target_count=config.TABLE_COLUMN_HEADERS['target_count'],
                col_target_dgsf=config.TABLE_COLUMN_HEADERS['target_dgsf'],
                col_actual_count=config.TABLE_COLUMN_HEADERS['actual_count'],
                col_actual_dgsf=config.TABLE_COLUMN_HEADERS['actual_dgsf'],
                col_count_delta=config.TABLE_COLUMN_HEADERS['count_delta'],
                col_dgsf_delta=config.TABLE_COLUMN_HEADERS['dgsf_delta'],
                col_dgsf_percentage=config.TABLE_COLUMN_HEADERS['dgsf_percentage'],
                col_status=config.TABLE_COLUMN_HEADERS['status'],
                col_match_quality=config.TABLE_COLUMN_HEADERS['match_quality'],
                table_rows=self._create_table_rows(matches),
                unmatched_section=self._create_unmatched_section(unmatched_areas, scheme_name)
            )
        
        html += """
        </div>
        
        <footer class="report-footer">
            <p>Report generated by Monitor Area System | {current_time}</p>
        </footer>
    </div>
    
    <script>
        {javascript}
    </script>
</body>
</html>
        """.format(current_time=current_time, javascript=self._get_javascript())
        
        return html
    
    def _create_table_rows(self, matches):
        """Create table rows for the comparison table"""
        rows = []
        for match in matches:
            status_class = match['status'].lower()
            count_delta_class = "positive" if match['count_delta'] >= 0 else "negative"
            dgsf_delta_class = "positive" if match['dgsf_delta'] >= 0 else "negative"
            percentage_class = "positive" if match['dgsf_percentage'] >= 0 else "negative"
            
            count_delta_str = "{:+,}".format(match['count_delta']) if match['count_delta'] else "0"
            dgsf_delta_str = "{:+,.0f}".format(match['dgsf_delta']) if match['dgsf_delta'] else "+0"
            percentage_str = "{:+.1f}%".format(match['dgsf_percentage']) if match['dgsf_percentage'] else "+0.0%"
            
            rows.append("""
                <tr class="status-{status_class}">
                    <td><strong>{room_name}</strong></td>
                    <td>{department}</td>
                    <td>{division}</td>
                    <td>{target_count}</td>
                    <td>{target_dgsf}</td>
                    <td>{actual_count}</td>
                    <td>{actual_dgsf}</td>
                    <td class="{count_delta_class}">{count_delta}</td>
                    <td class="{dgsf_delta_class}">{dgsf_delta}</td>
                    <td class="{percentage_class}">{percentage}</td>
                    <td><span class="status-badge {status_class}">{status_icon} {status}</span></td>
                    <td><span class="quality-badge {quality_class}">{match_quality}</span></td>
                </tr>
            """.format(
                status_class=status_class,
                room_name=match['room_name'],
                department=match['department'],
                division=match['division'],
                target_count="{:,}".format(match['target_count']),
                target_dgsf="{:,.0f}".format(match['target_dgsf']),
                actual_count="{:,}".format(match['actual_count']),
                actual_dgsf="{:,.0f}".format(match['actual_dgsf']),
                count_delta_class=count_delta_class,
                count_delta=count_delta_str,
                dgsf_delta_class=dgsf_delta_class,
                dgsf_delta=dgsf_delta_str,
                percentage_class=percentage_class,
                percentage=percentage_str,
                status_icon=self._get_status_icon(match['status']),
                status=match['status'],
                quality_class=match['match_quality'].lower(),
                match_quality=match['match_quality']
            ))
        
        return "".join(rows)
    
    def _create_unmatched_section(self, unmatched_areas, scheme_name=None):
        """
        Create section for unmatched areas
        
        Args:
            unmatched_areas: List of unmatched area objects
            scheme_name: Name of the scheme (optional)
            
        Returns:
            str: HTML for unmatched section
        """
        if not unmatched_areas:
            return ""
        
        unmatched_rows = []
        for area_object in unmatched_areas:
            # Get area data with 3 parameters
            area_sf = area_object.get('area_sf', 0)
            area_dept = area_object.get('department', '')
            area_type = area_object.get('program_type', '')
            area_detail = area_object.get('program_type_detail', '')
            
            unmatched_rows.append("""
                <tr>
                    <td>{area_detail}</td>
                    <td>{area_dept}</td>
                    <td>{area_type}</td>
                    <td>{area_sf} SF</td>
                    <td><span class="status-badge unmatched">🔍 Unmatched</span></td>
                </tr>
            """.format(
                area_detail=area_detail,
                area_dept=area_dept,
                area_type=area_type,
                area_sf="{:,.0f}".format(area_sf)
            ))
        
        section_title = "🔍 Unmatched Areas"
        if scheme_name:
            section_title = "{} - {}".format(section_title, scheme_name)
        
        return """
        <div class="unmatched-section">
            <h3>{section_title}</h3>
            <p>The following Revit areas were not matched to any Excel requirements:</p>
            <div class="table-container">
                <table class="unmatched-table">
                    <thead>
                        <tr>
                            <th>Area Name</th>
                            <th>Department</th>
                            <th>Program Type</th>
                            <th>Area (SF)</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {unmatched_rows}
                    </tbody>
                </table>
            </div>
        </div>
        """.format(
            section_title=section_title,
            unmatched_rows="".join(unmatched_rows)
        )
    
    def _get_status_icon(self, status):
        """Get icon for status"""
        icons = {
            "Fulfilled": "✅",
            "Partial": "⚠️",
            "Missing": "❌"
        }
        return icons.get(status, "❓")
    
    def _get_css_styles(self):
        """Get CSS styles for the report - Dark Professional Theme"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #e4e6eb;
            background: linear-gradient(135deg, #0f1419 0%, #1a1f2e 100%);
            min-height: 100vh;
        }
        
        .container {
            max-width: 1600px;
            margin: 0 auto;
            padding: 30px 20px;
        }
        
        .report-header {
            text-align: center;
            margin-bottom: 40px;
            padding: 30px;
            background: linear-gradient(135deg, #1e2936 0%, #2d3748 100%);
            border-radius: 12px;
            border: 1px solid #3a4556;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        
        .report-header h1 {
            color: #60a5fa;
            font-size: 2.8em;
            margin-bottom: 15px;
            font-weight: 700;
            text-shadow: 0 2px 10px rgba(96,165,250,0.3);
        }
        
        .report-info {
            color: #9ca3af;
            font-size: 0.95em;
        }
        
        .report-info strong {
            color: #d1d5db;
        }
        
        .summary-section, .status-summary, .comparison-section, .unmatched-section, .scheme-summary, .scheme-section {
            margin-bottom: 35px;
        }
        
        .summary-section h2, .status-summary h2, .comparison-section h2, .unmatched-section h2, .scheme-summary h2, .scheme-section h2 {
            color: #60a5fa;
            margin-bottom: 20px;
            font-size: 1.8em;
            font-weight: 600;
        }
        
        .unmatched-section h3 {
            color: #fbbf24;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .summary-cards, .scheme-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card, .scheme-card {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d4a73 100%);
            color: #e4e6eb;
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            border: 1px solid #3a5a8a;
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover, .scheme-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(96,165,250,0.2);
        }
        
        .card h3, .scheme-card h3 {
            font-size: 0.95em;
            margin-bottom: 12px;
            color: #93c5fd;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .card-value {
            font-size: 2.2em;
            font-weight: 700;
            margin-bottom: 8px;
            color: #60a5fa;
        }
        
        .card-label {
            font-size: 0.85em;
            color: #9ca3af;
        }
        
        .scheme-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 15px;
            margin-top: 15px;
        }
        
        .stat {
            text-align: center;
        }
        
        .stat-value {
            display: block;
            font-size: 1.5em;
            font-weight: 700;
            color: #60a5fa;
        }
        
        .stat-label {
            display: block;
            font-size: 0.8em;
            color: #9ca3af;
            margin-top: 4px;
        }
        
        .status-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
        }
        
        .status-card {
            padding: 25px;
            border-radius: 12px;
            text-align: center;
            color: #fff;
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 6px 20px rgba(0,0,0,0.3);
        }
        
        .status-card.fulfilled {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
        }
        
        .status-card.partial {
            background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
        }
        
        .status-card.missing {
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
        }
        
        .status-card h3 {
            margin-bottom: 12px;
            font-size: 1.1em;
        }
        
        .status-count {
            font-size: 2.5em;
            font-weight: 700;
        }
        
        .table-container {
            overflow-x: auto;
            border-radius: 12px;
            background: #1e2936;
            border: 1px solid #3a4556;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        
        .comparison-table, .unmatched-table {
            width: 100%;
            border-collapse: collapse;
            background-color: transparent;
        }
        
        .comparison-table th, .unmatched-table th {
            background: linear-gradient(135deg, #1e3a5f 0%, #2d4a73 100%);
            color: #93c5fd;
            padding: 16px 12px;
            text-align: left;
            font-weight: 600;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            position: sticky;
            top: 0;
            z-index: 10;
            border-bottom: 2px solid #60a5fa;
        }
        
        .comparison-table td, .unmatched-table td {
            padding: 14px 12px;
            border-bottom: 1px solid #374151;
            color: #d1d5db;
        }
        
        .comparison-table tbody tr, .unmatched-table tbody tr {
            background-color: #1e2936;
            transition: background-color 0.2s;
        }
        
        .comparison-table tr:hover, .unmatched-table tr:hover {
            background-color: #2d3748;
        }
        
        .status-fulfilled {
            border: 2px solid #10b981;
            background: linear-gradient(90deg, rgba(16,185,129,0.1) 0%, transparent 100%);
        }
        
        .status-partial {
            border: 2px solid #f59e0b;
            background: linear-gradient(90deg, rgba(245,158,11,0.1) 0%, transparent 100%);
        }
        
        .status-missing {
            border: 2px solid #ef4444;
            background: linear-gradient(90deg, rgba(239,68,68,0.1) 0%, transparent 100%);
        }
        
        .positive {
            color: #10b981;
            font-weight: 700;
        }
        
        .negative {
            color: #ef4444;
            font-weight: 700;
        }
        
        .status-badge {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.75em;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            display: inline-block;
        }
        
        .status-badge.fulfilled {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: #fff;
            border: 1px solid #10b981;
        }
        
        .status-badge.partial {
            background: linear-gradient(135deg, #d97706 0%, #f59e0b 100%);
            color: #fff;
            border: 1px solid #f59e0b;
        }
        
        .status-badge.missing {
            background: linear-gradient(135deg, #dc2626 0%, #ef4444 100%);
            color: #fff;
            border: 1px solid #ef4444;
        }
        
        .status-badge.unmatched {
            background: linear-gradient(135deg, #4b5563 0%, #6b7280 100%);
            color: #fff;
            border: 1px solid #6b7280;
        }
        
        .quality-badge {
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 0.7em;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .quality-badge.high {
            background-color: #0ea5e9;
            color: #fff;
            border: 1px solid #38bdf8;
        }
        
        .quality-badge.medium {
            background-color: #f59e0b;
            color: #fff;
            border: 1px solid #fbbf24;
        }
        
        .quality-badge.low, .quality-badge.no {
            background-color: #ef4444;
            color: #fff;
            border: 1px solid #f87171;
        }
        
        .report-footer {
            text-align: center;
            margin-top: 50px;
            padding: 25px;
            background: #1e2936;
            border-radius: 12px;
            border: 1px solid #3a4556;
            color: #9ca3af;
            font-size: 0.9em;
        }
        
        .scheme-comparisons {
            display: flex;
            flex-direction: column;
            gap: 30px;
        }
        
        .scheme-section {
            background: #1e2936;
            padding: 25px;
            border-radius: 12px;
            border: 1px solid #3a4556;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 15px 10px;
            }
            
            .summary-cards, .scheme-cards {
                grid-template-columns: 1fr;
            }
            
            .status-cards {
                grid-template-columns: 1fr;
            }
            
            .report-header h1 {
                font-size: 2em;
            }
            
            .card, .scheme-card {
                padding: 20px;
            }
        }
        """
    
    def _get_javascript(self):
        """Get JavaScript for interactive features"""
        return """
        document.addEventListener('DOMContentLoaded', function() {
            const table = document.querySelector('.comparison-table');
            if (table) {
                const headers = table.querySelectorAll('th');
                headers.forEach((header, index) => {
                    header.style.cursor = 'pointer';
                    header.addEventListener('click', () => {
                        sortTable(table, index);
                    });
                });
            }
        });
        
        function sortTable(table, columnIndex) {
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));
            
            rows.sort((a, b) => {
                const aValue = a.cells[columnIndex].textContent.trim();
                const bValue = b.cells[columnIndex].textContent.trim();
                
                const aNum = parseFloat(aValue.replace(/[^0-9.-]/g, ''));
                const bNum = parseFloat(bValue.replace(/[^0-9.-]/g, ''));
                
                if (!isNaN(aNum) && !isNaN(bNum)) {
                    return aNum - bNum;
                }
                
                return aValue.localeCompare(bValue);
            });
            
            rows.forEach(row => tbody.appendChild(row));
        }
        """
    
    def open_report_in_browser(self, filepath=None):
        """Open the report in the default browser"""
        if filepath is None:
            filepath = os.path.join(self.reports_dir, config.LATEST_REPORT_FILENAME)
        
        if os.path.exists(filepath):
            webbrowser.open("file://{}".format(os.path.abspath(filepath)))
            return True
        else:
            return False
