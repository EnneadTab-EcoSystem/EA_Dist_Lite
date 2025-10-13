#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
HTML Export Module - Handles area matching and HTML report generation
Uses exact matching on 3 parameters: Department, Program Type, Program Type Detail
"""

import os
import webbrowser
import io
from datetime import datetime
import config


class AreaMatcher:
    """Exact matching between Excel requirements and Revit areas using 3 parameters"""
    
    def _safe_int(self, value):
        """Safely convert value to integer"""
        try:
            return int(float(value)) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _safe_float(self, value):
        """Safely convert value to float"""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
    
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
                total_sf = sum(self._safe_float(area['area_sf']) for area in areas_list)
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
        excel_row_index = 0  # Track Excel row order
        
        for room_key, requirement in excel_data.items():
            excel_row_index += 1
            # Extract requirement data from RowData object using Excel column names
            room_name = getattr(requirement, config.PROGRAM_TYPE_DETAIL_KEY[config.APP_EXCEL], room_key)
            department = getattr(requirement, config.DEPARTMENT_KEY[config.APP_EXCEL], '')
            program_type = getattr(requirement, config.PROGRAM_TYPE_KEY[config.APP_EXCEL], '')
            target_count = getattr(requirement, config.COUNT_KEY[config.APP_EXCEL], 0)
            target_dgsf = getattr(requirement, config.SCALED_DGSF_KEY[config.APP_EXCEL], 0)
            color = getattr(requirement, 'COLOR', None)  # Extract color from Excel
            
            # Convert to numeric types to ensure proper calculations
            target_count = self._safe_int(target_count)
            target_dgsf = self._safe_float(target_dgsf)
            
            # Find matching Revit areas using exact 3-parameter match
            matching_areas = self._find_matching_areas(
                room_name,  # program_type_detail
                department, 
                program_type, 
                areas_list
            )
            
            # Calculate actual counts and areas
            actual_count = len(matching_areas)
            actual_dgsf = sum(self._safe_float(area['area_sf']) for area in matching_areas)
            
            # Calculate deltas (handle None values)
            # If target is None or 0, delta should be None (no requirement)
            if target_count is None or target_count == 0:
                count_delta = None  # No count requirement
            else:
                count_delta = actual_count - target_count
                
            if target_dgsf is None or target_dgsf == 0:
                dgsf_delta = None  # No area requirement
                dgsf_percentage = None
            else:
                dgsf_delta = actual_dgsf - target_dgsf
                dgsf_percentage = (dgsf_delta / target_dgsf * 100)
            
            # Determine status
            status = self._determine_status(
                target_count, 
                target_dgsf, 
                actual_count, 
                actual_dgsf
            )
            
            # Get level information from matching areas
            levels = [area.get('level_name', 'Unknown Level') for area in matching_areas]
            level_summary = ', '.join(sorted(set(levels))) if levels else 'No Areas'
            
            match_result = {
                'excel_row_index': excel_row_index,  # Track Excel order
                'room_name': room_name,
                'department': department,
                'division': program_type,
                'color': color,  # Include color from Excel
                'target_count': target_count,
                'target_dgsf': target_dgsf,
                'actual_count': actual_count,
                'actual_dgsf': actual_dgsf,
                'count_delta': count_delta,
                'dgsf_delta': dgsf_delta,
                'dgsf_percentage': dgsf_percentage,
                'status': status,
                'matching_areas': matching_areas,
                'level_summary': level_summary,
                'match_quality': self._calculate_match_quality_simple(matching_areas, status)
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
        """Determine fulfillment status with proper overage handling"""
        # Define tolerance limits
        tolerance_percentage = config.AREA_TOLERANCE_PERCENTAGE / 100.0
        
        # Handle None/0 values (no requirement)
        has_count_requirement = target_count is not None and target_count > 0
        has_area_requirement = target_dgsf is not None and target_dgsf > 0
        
        # If no requirements at all, return "No Requirement"
        if not has_count_requirement and not has_area_requirement:
            return "No Requirement"
        
        # Check if we have any areas at all
        if actual_count == 0 and actual_dgsf == 0:
            return "Missing"
        
        # Calculate acceptable ranges for area (only if there's an area requirement)
        if has_area_requirement:
            min_area = target_dgsf * (1 - tolerance_percentage)
            max_area = target_dgsf * (1 + tolerance_percentage)
            area_overage_percentage = (actual_dgsf - target_dgsf) / target_dgsf
        else:
            area_overage_percentage = 0
        
        # Calculate count overage (only if there's a count requirement)
        if has_count_requirement:
            count_overage_percentage = (actual_count - target_count) / float(target_count)
        else:
            count_overage_percentage = 0
        
        # Check for excessive overage (more than 200% over target)
        if area_overage_percentage > 2.0 or count_overage_percentage > 2.0:
            return "Excessive"
        
        # Check fulfillment based on what requirements exist
        if has_count_requirement and has_area_requirement:
            # Both requirements exist - check both
            count_met = actual_count >= target_count
            area_met = min_area <= actual_dgsf <= max_area
            if count_met and area_met:
                return "Fulfilled"
            elif actual_count > 0 and actual_dgsf > 0:
                return "Partial"
        elif has_count_requirement:
            # Only count requirement exists
            if actual_count >= target_count:
                return "Fulfilled"
            elif actual_count > 0:
                return "Partial"
        elif has_area_requirement:
            # Only area requirement exists
            if min_area <= actual_dgsf <= max_area:
                return "Fulfilled"
            elif actual_dgsf > 0:
                return "Partial"
        
        return "Missing"
    
    def _calculate_match_quality_simple(self, matching_areas, status=None):
        """Calculate overall match quality based on number of matches and status"""
        if not matching_areas:
            return "No Match"
        
        # If status is Excessive, quality should be Low regardless of match count
        if status == "Excessive":
            return "Low"
        
        # For other statuses, base quality on number of matches
        if len(matching_areas) == 1:
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
    
    def _safe_int(self, value):
        """Safely convert value to integer"""
        try:
            return int(float(value)) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _safe_float(self, value):
        """Safely convert value to float"""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def __init__(self):
        self.reports_dir = os.path.join(os.path.dirname(__file__), config.REPORTS_DIR)
        
        # Create reports directory if it doesn't exist
        if not os.path.exists(self.reports_dir):
            os.makedirs(self.reports_dir)
        
        # Initialize color hierarchy
        self.color_hierarchy = {
            'department': {},
            'division': {},
            'room_name': {}
        }
    
    def get_color(self, level, name, fallback='#6b7280'):
        """
        Get color from hierarchy with fallback logic.
        
        Args:
            level: 'department', 'division', or 'room_name'
            name: Name to look up
            fallback: Default color if not found
            
        Returns:
            str: Hex color code
        """
        return self.color_hierarchy.get(level, {}).get(name, fallback)
    
    def generate_html_report(self, excel_data, revit_data, color_hierarchy=None):
        """
        Generate separate HTML reports for each scheme
        
        Args:
            excel_data: Dictionary of Excel data with RowData objects
            revit_data: Dictionary of area data by scheme {scheme_name: [areas]}
            color_hierarchy: Dict with color mappings at department/division/room levels
            
        Returns:
            tuple: (list of filepaths, all_matches, all_unmatched_areas)
        """
        # Store color hierarchy for use in HTML generation
        self.color_hierarchy = color_hierarchy or {
            'department': {},
            'division': {},
            'room_name': {}
        }
        
        # Match areas to requirements
        matcher = AreaMatcher()
        all_matches = matcher.match_areas_to_requirements(excel_data, revit_data)
        
        # Get unmatched areas for each scheme
        all_unmatched_areas = {}
        for scheme_name, areas_list in revit_data.items():
            if isinstance(areas_list, list):
                unmatched = matcher.get_unmatched_areas(excel_data, areas_list)
                all_unmatched_areas[scheme_name] = unmatched
        
        # Generate one HTML per scheme
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        filepaths = []
        
        for scheme_name, scheme_data in all_matches.items():
            # Extract matches for this scheme
            matches = scheme_data.get('matches', [])
            unmatched_areas = all_unmatched_areas.get(scheme_name, {})
            
            # Generate HTML for this scheme
            html_content = self._create_scheme_html(
                scheme_name=scheme_name,
                matches=matches,
                unmatched_areas=unmatched_areas,
                current_time=current_time
            )
            
            # Save to scheme-specific file
            safe_scheme_name = scheme_name.replace(" ", "_").replace("/", "_")
            filename = "area_report_{}_{}.html".format(safe_scheme_name, timestamp)
            filepath = os.path.join(self.reports_dir, filename)
            
            with io.open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            filepaths.append(filepath)
        
        # Save the first (or only) report as latest_report.html for easy access
        if filepaths:
            latest_path = os.path.join(self.reports_dir, config.LATEST_REPORT_FILENAME)
            with io.open(latest_path, 'w', encoding='utf-8') as f:
                # Use the first scheme's HTML as the latest
                first_scheme = list(all_matches.keys())[0]
                first_matches = all_matches[first_scheme].get('matches', [])
                first_unmatched = all_unmatched_areas.get(first_scheme, {})
                latest_html = self._create_scheme_html(
                    scheme_name=first_scheme,
                    matches=first_matches,
                    unmatched_areas=first_unmatched,
                    current_time=current_time
                )
                f.write(latest_html)
        
        return filepaths, all_matches, all_unmatched_areas
    
    def _create_scheme_html(self, scheme_name, matches, unmatched_areas, current_time):
        """Create HTML for single scheme"""
        # Calculate summary statistics
        total_target_count = sum(match['target_count'] for match in matches if match['target_count'] is not None)
        total_actual_count = sum(match['actual_count'] for match in matches if match['actual_count'] is not None)
        total_target_dgsf = sum(match['target_dgsf'] for match in matches if match['target_dgsf'] is not None)
        total_actual_dgsf = sum(match['actual_dgsf'] for match in matches if match['actual_dgsf'] is not None)
        
        fulfilled_count = sum(1 for match in matches if match['status'] == 'Fulfilled')
        partial_count = sum(1 for match in matches if match['status'] == 'Partial')
        missing_count = sum(1 for match in matches if match['status'] == 'Missing')
        
        # Count alerts for high differences (skip None values)
        high_count_delta_alerts = sum(1 for match in matches if match['count_delta'] is not None and abs(match['count_delta']) >= config.COUNT_DELTA_ALERT_THRESHOLD)
        high_area_delta_alerts = sum(1 for match in matches if match['dgsf_percentage'] is not None and abs(match['dgsf_percentage']) >= config.AREA_PERCENTAGE_ALERT_THRESHOLD)
        extreme_difference_alerts = sum(1 for match in matches if 
            match['count_delta'] is not None and match['dgsf_percentage'] is not None and
            abs(match['count_delta']) >= config.COUNT_DELTA_ALERT_THRESHOLD and 
            abs(match['dgsf_percentage']) >= config.AREA_PERCENTAGE_ALERT_THRESHOLD)
        
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
                <p><strong>Area Scheme:</strong> {scheme_name}</p>
            </div>
        </header>
        
        <div class="department-summary-section">
            <h2>📊 Department Fulfillment Summary</h2>
            {department_summary_table}
        </div>
        
        <div class="comparison-section">
            <h2>📋 Detailed Comparison</h2>
            <div class="table-container">
                <table class="comparison-table">
                    <thead>
                        <tr>
                            <th>{col_department}</th>
                            <th>{col_program_type}</th>
                            <th>{col_area_detail}</th>
                            <th>{col_target_count}</th>
                            <th>{col_target_dgsf}</th>
                            <th>Level Summary</th>
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
                <div class="card">
                    <h3>Count Alerts</h3>
                    <div class="card-value">{high_count_delta_alerts}</div>
                    <div class="card-label">High Count Differences</div>
                </div>
                <div class="card">
                    <h3>Area Alerts</h3>
                    <div class="card-value">{high_area_delta_alerts}</div>
                    <div class="card-label">High Area Differences</div>
                </div>
                <div class="card">
                    <h3>Extreme Alerts</h3>
                    <div class="card-value">{extreme_difference_alerts}</div>
                    <div class="card-label">Both High Differences</div>
                </div>
            </div>
        </div>
        
        <div class="status-summary">
            <h2>📈 Status Breakdown</h2>
            <div class="status-cards">
                <div class="status-card fulfilled">
                    <h3>✓ Fulfilled</h3>
                    <div class="status-count">{fulfilled_count}</div>
                </div>
                <div class="status-card partial">
                    <h3>△ Partial</h3>
                    <div class="status-count">{partial_count}</div>
                </div>
                <div class="status-card missing">
                    <h3>✕ Missing</h3>
                    <div class="status-count">{missing_count}</div>
                </div>
            </div>
        </div>
        
        <footer class="report-footer">
            <p>Report generated by Monitor Area System | {current_time}</p>
            <p style="margin-top: 10px; font-size: 0.9em; color: #9ca3af;">
                🦆 Powered by <strong style="color: #60a5fa;">EnneadTab</strong> | 
                For feature requests, contact <strong style="color: #60a5fa;">Sen Zhang</strong>
            </p>
        </footer>
    </div>
    
    <!-- Sticky Search Bar at Bottom - Outside container for true fixed positioning -->
    <div class="search-bar-container">
        <div class="search-bar-content">
            <div style="position: relative;">
                <input type="text" id="fuzzySearch" placeholder="🔍 Filter by department, division, or function... (fuzzy search enabled)" />
                <button id="clearSearch" class="clear-search-btn" style="display: none;" onclick="clearSearchFilter()">✕</button>
            </div>
            <div id="searchStatus" class="search-status"></div>
        </div>
    </div>
    
    <!-- Right-Click Context Menu -->
    <div id="contextMenu" class="context-menu">
        <div class="context-menu-item" onclick="returnToTop()">
            <span class="context-menu-icon">⬆️</span>
            <span>Return to Top</span>
        </div>
        <div class="context-menu-item" onclick="collapseAllDepartments()">
            <span class="context-menu-icon">▲</span>
            <span>Collapse All Departments</span>
        </div>
        <div class="context-menu-item" onclick="expandAllDepartments()">
            <span class="context-menu-icon">▼</span>
            <span>Expand All Departments</span>
        </div>
    </div>
    
    <!-- Minimap Navigation Panel -->
    <div class="minimap-toggle" onclick="toggleMinimap()" title="Toggle Navigation Panel">
        🗺️ Nav
    </div>
    <nav class="minimap-nav" id="minimapNav">
        <div class="minimap-title">📍 Quick Navigation</div>
        <div class="minimap-item" onclick="scrollToSection('report-header')" data-section="report-header">
            <span class="minimap-icon">🏥</span>
            <span>Report Header</span>
        </div>
        <div class="minimap-item" onclick="scrollToSection('department-summary-section')" data-section="department-summary-section">
            <span class="minimap-icon">📊</span>
            <span>Department Summary</span>
        </div>
        <div class="minimap-item" onclick="scrollToSection('comparison-section')" data-section="comparison-section">
            <span class="minimap-icon">📋</span>
            <span>Detailed Comparison</span>
        </div>
        <div class="minimap-item" onclick="scrollToSection('unmatched-section')" data-section="unmatched-section">
            <span class="minimap-icon">⚠️</span>
            <span>Unmatched Areas</span>
        </div>
        <div class="minimap-item" onclick="scrollToSection('summary-section')" data-section="summary-section">
            <span class="minimap-icon">📊</span>
            <span>Summary</span>
        </div>
        <div class="minimap-item" onclick="scrollToSection('status-summary')" data-section="status-summary">
            <span class="minimap-icon">📈</span>
            <span>Status Breakdown</span>
        </div>
    </nav>
    
    <script src="https://cdn.jsdelivr.net/npm/fuse.js@6.6.2"></script>
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
            scheme_name=scheme_name,
            total_reqs=len(matches),
            target_count="{:,}".format(int(float(total_target_count))),
            actual_count="{:,}".format(int(float(total_actual_count))),
            target_dgsf="{:,.0f}".format(float(self._safe_float(total_target_dgsf))),
            actual_dgsf="{:,.0f}".format(float(self._safe_float(total_actual_dgsf))),
            fulfilled_count=fulfilled_count,
            partial_count=partial_count,
            missing_count=missing_count,
            high_count_delta_alerts=high_count_delta_alerts,
            high_area_delta_alerts=high_area_delta_alerts,
            extreme_difference_alerts=extreme_difference_alerts,
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
            unmatched_section=self._create_unmatched_section(unmatched_areas, matches),
            department_summary_table=self._create_department_summary_table(matches),
            javascript=self._get_javascript()
        )
        return html
    
    def _create_table_rows(self, matches):
        """Create table rows for the comparison table, grouped by department, preserving Excel order"""
        rows = []
        
        # Group matches by department while preserving Excel order
        from collections import OrderedDict
        department_groups = OrderedDict()
        for match in matches:
            dept = match['department'] or 'No Department'
            if dept not in department_groups:
                department_groups[dept] = []
            department_groups[dept].append(match)
        
        # Sort department groups by the first occurrence in Excel (using excel_row_index of first item)
        sorted_departments = sorted(department_groups.items(), key=lambda x: x[1][0]['excel_row_index'])
        
        # Generate rows for each department group
        for dept_index, (dept_name, dept_matches) in enumerate(sorted_departments):
            # Add department header row - use department-level color from hierarchy
            dept_color = self.get_color('department', dept_name)
            # Fallback to first room's color if no department color found
            if dept_color == '#6b7280' and dept_matches:
                dept_color = dept_matches[0].get('color', '#6b7280')
            
            # Make department header collapsible with toggle icon
            dept_id = "dept_{}".format(dept_index)
            rows.append("""
                <tr class="department-header" data-dept-id="{dept_id}" onclick="toggleDepartment('{dept_id}')" style="background: linear-gradient(90deg, {color} 0%, rgba(17, 24, 39, 0.8) 100%); cursor: pointer;">
                    <td colspan="13" style="padding: 12px 16px; font-weight: 600; font-size: 1.1em; color: white; border-left: 4px solid {color};">
                        <span class="collapse-icon" id="icon_{dept_id}" style="display: inline-block; margin-right: 8px; transition: transform 0.3s ease;">▼</span>
                        <span style="display: inline-block; width: 12px; height: 12px; background: {color}; border-radius: 50%; margin-right: 8px;"></span>
                        {dept_name}
                    </td>
                </tr>
            """.format(color=dept_color, dept_name=dept_name, dept_id=dept_id))
            
            # Sort matches within department by Excel order
            dept_matches_sorted = sorted(dept_matches, key=lambda x: x['excel_row_index'])
            
            # Calculate department totals
            dept_target_count = sum(m['target_count'] for m in dept_matches_sorted if m['target_count'] is not None)
            dept_target_dgsf = sum(m['target_dgsf'] for m in dept_matches_sorted if m['target_dgsf'] is not None)
            dept_actual_count = sum(m['actual_count'] for m in dept_matches_sorted)
            dept_actual_dgsf = sum(m['actual_dgsf'] for m in dept_matches_sorted)
            dept_count_delta = dept_actual_count - dept_target_count if dept_target_count > 0 else None
            dept_dgsf_delta = dept_actual_dgsf - dept_target_dgsf if dept_target_dgsf > 0 else None
            
            # Add rows for this department
            for match in dept_matches_sorted:
                status_class = match['status'].lower()
                
                # Check for high differences and apply alert styling (handle None values)
                count_delta_abs = abs(match['count_delta']) if match['count_delta'] is not None else 0
                area_percentage_abs = abs(match['dgsf_percentage']) if match['dgsf_percentage'] is not None else 0
                
                # Determine alert classes (handle None values)
                if match['count_delta'] is None:
                    count_delta_class = "neutral"
                else:
                    count_delta_class = "positive" if match['count_delta'] >= 0 else "negative"
                    
                if match['dgsf_delta'] is None:
                    dgsf_delta_class = "neutral"
                else:
                    dgsf_delta_class = "positive" if match['dgsf_delta'] >= 0 else "negative"
                    
                if match['dgsf_percentage'] is None:
                    percentage_class = "neutral"
                else:
                    percentage_class = "positive" if match['dgsf_percentage'] >= 0 else "negative"
                
                # Apply alert styling for high differences
                if count_delta_abs >= config.COUNT_DELTA_ALERT_THRESHOLD:
                    count_delta_class = "alert-count-delta"
                
                if area_percentage_abs >= config.AREA_PERCENTAGE_ALERT_THRESHOLD:
                    percentage_class = "alert-area-delta"
                
                # Check if entire row should be highlighted for extreme differences
                row_alert_class = ""
                if (count_delta_abs >= config.COUNT_DELTA_ALERT_THRESHOLD and 
                    area_percentage_abs >= config.AREA_PERCENTAGE_ALERT_THRESHOLD):
                    row_alert_class = "alert-high-difference"
                
                # Format count delta with descriptive text
                if match['count_delta'] is None:
                    count_delta_str = "N/A (No Req.)"
                elif match['count_delta'] > 0:
                    count_delta_str = "Exceeding {}".format(abs(match['count_delta']))
                elif match['count_delta'] < 0:
                    count_delta_str = "Missing {}".format(abs(match['count_delta']))
                else:
                    count_delta_str = "Exact Match"
                
                # Format area delta with descriptive text
                dgsf_delta = match['dgsf_delta']
                if dgsf_delta is None:
                    dgsf_delta_str = "N/A (No Req.)"
                elif dgsf_delta > 0:
                    dgsf_delta_str = "Exceeding {:,.0f} SF".format(float(abs(dgsf_delta)))
                elif dgsf_delta < 0:
                    dgsf_delta_str = "Missing {:,.0f} SF".format(float(abs(dgsf_delta)))
                else:
                    dgsf_delta_str = "Exact Match"
                
                # Format percentage
                if match['dgsf_percentage'] is None:
                    percentage_str = "N/A"
                else:
                    percentage_str = "{:+.1f}%".format(float(self._safe_float(match['dgsf_percentage'])))
                
                rows.append("""
                    <tr class="status-{status_class} {row_alert_class} dept-row" data-dept="{dept_id}" data-search-dept="{department}" data-search-division="{division}" data-search-function="{room_name}">
                        <td class="col-dept">{department}</td>
                        <td class="col-division">{division}</td>
                        <td class="col-function"><strong>{room_name}</strong></td>
                        <td class="col-count">{target_count}</td>
                        <td class="col-area">{target_dgsf}</td>
                        <td class="col-level">{level_summary}</td>
                        <td class="col-count">{actual_count}</td>
                        <td class="col-area">{actual_dgsf}</td>
                        <td class="col-delta {count_delta_class}">{count_delta}</td>
                        <td class="col-delta {dgsf_delta_class}">{dgsf_delta}</td>
                        <td class="col-delta {percentage_class}">{percentage}</td>
                        <td class="col-status"><span class="status-badge {status_class}">{status_icon} {status}</span></td>
                        <td class="col-quality"><span class="quality-badge {quality_class}">{match_quality}</span></td>
                    </tr>
                """.format(
                    dept_id=dept_id,
                    status_class=status_class,
                    row_alert_class=row_alert_class,
                    department=match['department'],
                    division=match['division'],
                    room_name=match['room_name'],
                    level_summary=match['level_summary'],
                    target_count="Any" if (match['target_count'] is None or match['target_count'] == 0) else "{:,}".format(int(float(match['target_count']))),
                    target_dgsf="N/A" if (match['target_dgsf'] is None or match['target_dgsf'] == 0) else "{:,.0f}".format(float(self._safe_float(match['target_dgsf']))),
                    actual_count="{:,}".format(int(float(match['actual_count']))),
                    actual_dgsf="{:,.0f}".format(float(self._safe_float(match['actual_dgsf']))),
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
    
    def _create_department_summary_table(self, matches):
        """Create department-level fulfillment summary table with visual charts, preserving Excel order"""
        from collections import OrderedDict
        import json
        
        # Group matches by department
        department_groups = OrderedDict()
        for match in matches:
            dept = match['department'] or 'No Department'
            if dept not in department_groups:
                department_groups[dept] = {
                    'matches': []
                }
            department_groups[dept]['matches'].append(match)
        
        # Sort departments by the first occurrence in Excel (using excel_row_index of first item)
        sorted_departments = sorted(department_groups.items(), key=lambda x: x[1]['matches'][0]['excel_row_index'])
        
        # Data for charts
        chart_data = {
            'departments': [],
            'target_dgsf': [],
            'actual_dgsf': [],
            'colors': [],
            'percentages': []
        }
        
        # Generate department summary rows
        rows = []
        for dept_name, dept_data in sorted_departments:
            dept_matches = dept_data['matches']
            # Use department-level color from hierarchy
            dept_color = self.get_color('department', dept_name)
            # Fallback to first match's color if no department color found
            if dept_color == '#6b7280' and dept_matches:
                dept_color = dept_matches[0].get('color', '#6b7280')
            
            # Calculate department totals
            dept_target_count = sum(m['target_count'] for m in dept_matches if m['target_count'] is not None)
            dept_target_dgsf = sum(m['target_dgsf'] for m in dept_matches if m['target_dgsf'] is not None)
            dept_actual_count = sum(m['actual_count'] for m in dept_matches)
            dept_actual_dgsf = sum(m['actual_dgsf'] for m in dept_matches)
            
            # Calculate deltas and percentages
            if dept_target_count > 0:
                dept_count_delta = dept_actual_count - dept_target_count
                dept_count_percentage = (dept_count_delta / float(dept_target_count) * 100) if dept_target_count > 0 else 0
            else:
                dept_count_delta = None
                dept_count_percentage = None
                
            if dept_target_dgsf > 0:
                dept_dgsf_delta = dept_actual_dgsf - dept_target_dgsf
                dept_dgsf_percentage = (dept_dgsf_delta / dept_target_dgsf * 100) if dept_target_dgsf > 0 else 0
            else:
                dept_dgsf_delta = None
                dept_dgsf_percentage = None
            
            # Add to chart data
            chart_data['departments'].append(dept_name)
            chart_data['target_dgsf'].append(float(dept_target_dgsf) if dept_target_dgsf else 0)
            chart_data['actual_dgsf'].append(float(dept_actual_dgsf) if dept_actual_dgsf else 0)
            chart_data['colors'].append(dept_color)
            chart_data['percentages'].append(float(dept_dgsf_percentage) if dept_dgsf_percentage is not None else 0)
            
            # Status styling
            if dept_dgsf_percentage is not None:
                if abs(dept_dgsf_percentage) <= 5:
                    status_class = "fulfilled"
                    status_icon = "✓"
                    status_text = "On Target"
                elif dept_dgsf_percentage > 5:
                    status_class = "excessive"
                    status_icon = "↑"
                    status_text = "Over"
                else:
                    status_class = "partial"
                    status_icon = "△"
                    status_text = "Under"
            else:
                status_class = "no requirement"
                status_icon = "—"
                status_text = "N/A"
            
            # Format values
            count_delta_str = "N/A" if dept_count_delta is None else "{:+d}".format(int(dept_count_delta))
            dgsf_delta_str = "N/A" if dept_dgsf_delta is None else "{:+,.0f} SF".format(float(dept_dgsf_delta))
            dgsf_pct_str = "N/A" if dept_dgsf_percentage is None else "{:+.1f}%".format(float(dept_dgsf_percentage))
            
            rows.append("""
                <tr style="border-left: 4px solid {color};">
                    <td style="font-weight: 600;">
                        <span style="display: inline-block; width: 10px; height: 10px; background: {color}; border-radius: 50%; margin-right: 8px;"></span>
                        {dept_name}
                    </td>
                    <td class="col-count">{target_count}</td>
                    <td class="col-area">{target_dgsf}</td>
                    <td class="col-count">{actual_count}</td>
                    <td class="col-area">{actual_dgsf}</td>
                    <td class="col-delta">{count_delta}</td>
                    <td class="col-delta">{dgsf_delta}</td>
                    <td class="col-delta">{dgsf_pct}</td>
                    <td class="col-status"><span class="status-badge {status_class}">{status_icon} {status_text}</span></td>
                </tr>
            """.format(
                color=dept_color,
                dept_name=dept_name,
                target_count="Any" if dept_target_count == 0 else "{:,}".format(int(float(dept_target_count))),
                target_dgsf="N/A" if dept_target_dgsf == 0 else "{:,.0f}".format(float(dept_target_dgsf)),
                actual_count="{:,}".format(int(float(dept_actual_count))),
                actual_dgsf="{:,.0f}".format(float(dept_actual_dgsf)),
                count_delta=count_delta_str,
                dgsf_delta=dgsf_delta_str,
                dgsf_pct=dgsf_pct_str,
                status_class=status_class.lower().replace(" ", "_"),
                status_icon=status_icon,
                status_text=status_text
            ))
        
        # Serialize chart data to JSON for JavaScript
        chart_data_json = json.dumps(chart_data)
        
        table_html = """
            <div class="department-summary-container">
                <!-- Charts Section -->
                <div class="charts-section" style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px; margin-bottom: 32px;">
                    <div class="chart-card" style="background: #1e293b; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        <h3 style="color: #e2e8f0; margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">📊 Target vs Actual DGSF</h3>
                        <canvas id="deptComparisonChart" style="max-height: 400px;"></canvas>
                    </div>
                    <div class="chart-card" style="background: #1e293b; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.3);">
                        <h3 style="color: #e2e8f0; margin: 0 0 16px 0; font-size: 16px; font-weight: 600;">📈 Fulfillment Percentage</h3>
                        <canvas id="deptPercentageChart" style="max-height: 400px;"></canvas>
                    </div>
                </div>
                
                <!-- Collapsible Data Table Section -->
                <div class="table-toggle-section" style="margin-top: 24px;">
                    <button onclick="toggleDepartmentTable()" 
                            style="background: #374151; color: #e5e7eb; border: none; padding: 12px 24px; 
                                   border-radius: 8px; cursor: pointer; font-size: 14px; font-weight: 500;
                                   transition: all 0.3s ease; display: flex; align-items: center; gap: 8px;
                                   margin: 0 auto;">
                        <span id="tableToggleIcon">▼</span>
                        <span id="tableToggleText">Show Detailed Table</span>
                    </button>
                </div>
                
                <div id="departmentTableContainer" class="department-summary-table" style="display: none; margin-top: 16px; opacity: 0; transition: opacity 0.3s ease;">
                    <table class="comparison-table">
                        <thead>
                            <tr>
                                <th style="width: 20%;">Department</th>
                                <th style="width: 10%;">Target Count</th>
                                <th style="width: 12%;">Target DGSF</th>
                                <th style="width: 10%;">Actual Count</th>
                                <th style="width: 12%;">Actual DGSF</th>
                                <th style="width: 10%;">Count Δ</th>
                                <th style="width: 12%;">DGSF Δ</th>
                                <th style="width: 8%;">DGSF %</th>
                                <th style="width: 10%;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows}
                        </tbody>
                    </table>
                </div>
            </div>
            
            <script id="departmentChartData" type="application/json">
            {chart_data_json}
            </script>
            
            <script>
                function toggleDepartmentTable() {{
                    const container = document.getElementById('departmentTableContainer');
                    const icon = document.getElementById('tableToggleIcon');
                    const text = document.getElementById('tableToggleText');
                    
                    if (container.style.display === 'none') {{
                        container.style.display = 'block';
                        setTimeout(() => {{ container.style.opacity = '1'; }}, 10);
                        icon.textContent = '▲';
                        text.textContent = 'Hide Detailed Table';
                    }} else {{
                        container.style.opacity = '0';
                        setTimeout(() => {{ container.style.display = 'none'; }}, 300);
                        icon.textContent = '▼';
                        text.textContent = 'Show Detailed Table';
                    }}
                }}
            </script>
        """.format(rows="".join(rows), chart_data_json=chart_data_json)
        
        return table_html
    
    def _create_unmatched_section(self, unmatched_areas, valid_matches=None, scheme_name=None):
        """
        Create section for unmatched areas with suggestions
        
        Args:
            unmatched_areas: List of unmatched area objects
            valid_matches: List of valid match dictionaries (for suggestions)
            scheme_name: Name of the scheme (optional)
            
        Returns:
            str: HTML for unmatched section
        """
        if not unmatched_areas:
            return ""
        
        # Build list of valid items for fuzzy matching suggestions
        valid_items = []
        if valid_matches:
            for match in valid_matches:
                valid_items.append({
                    'department': match.get('department', ''),
                    'division': match.get('division', ''),
                    'function': match.get('room_name', ''),
                    'combined': "{}-{}-{}".format(
                        match.get('department', ''),
                        match.get('division', ''),
                        match.get('room_name', '')
                    )
                })
        
        def find_best_suggestion(unmatched_dept, unmatched_div, unmatched_func):
            """Find the closest matching valid item using fuzzy matching"""
            if not valid_items:
                return None
            
            best_match = None
            best_score = float('inf')
            
            for valid_item in valid_items:
                # Calculate similarity score (simple approach)
                # Check if any component matches exactly
                dept_match = unmatched_dept.lower() == valid_item['department'].lower()
                div_match = unmatched_div.lower() == valid_item['division'].lower()
                func_match = unmatched_func.lower() == valid_item['function'].lower()
                
                # Score based on matches (lower is better)
                score = 3  # Start with worst case
                if dept_match:
                    score -= 1
                if div_match:
                    score -= 1
                if func_match:
                    score -= 1
                
                # Also check substring matches
                if not dept_match and unmatched_dept.lower() in valid_item['department'].lower():
                    score -= 0.3
                if not div_match and unmatched_div.lower() in valid_item['division'].lower():
                    score -= 0.3
                if not func_match and unmatched_func.lower() in valid_item['function'].lower():
                    score -= 0.3
                
                if score < best_score:
                    best_score = score
                    best_match = valid_item
            
            # Only return suggestion if there's at least one partial match
            if best_match and best_score < 3:
                return best_match
            return None
        
        # Group unmatched areas by level
        areas_by_level = {}
        for area_object in unmatched_areas:
            level_name = area_object.get('level_name', 'Unknown Level')
            if level_name not in areas_by_level:
                areas_by_level[level_name] = []
            areas_by_level[level_name].append(area_object)
        
        # Create HTML for each level
        level_sections = []
        for level_name, level_areas in sorted(areas_by_level.items()):
            level_rows = []
            level_total_sf = 0
            
            for area_object in level_areas:
                area_sf = area_object.get('area_sf', 0)
                area_dept = area_object.get('department', '')
                area_type = area_object.get('program_type', '')
                area_detail = area_object.get('program_type_detail', '')
                creator = area_object.get('creator', 'Unknown')
                last_editor = area_object.get('last_editor', 'Unknown')
                level_total_sf += area_sf
                
                # Find best suggestion for this unmatched area
                suggestion = find_best_suggestion(area_dept, area_type, area_detail)
                if suggestion:
                    suggestion_text = '<span class="suggestion-text">Do you mean <strong>{}-{}-{}</strong>?</span>'.format(
                        suggestion['department'],
                        suggestion['division'],
                        suggestion['function']
                    )
                else:
                    suggestion_text = '<span style="color: #6b7280;">No suggestion available</span>'
                
                level_rows.append("""
                    <tr>
                        <td class="col-dept">{area_dept}</td>
                        <td class="col-division">{area_type}</td>
                        <td class="col-function">{area_detail}</td>
                        <td class="col-area">{area_sf} SF</td>
                        <td class="col-level">{creator}</td>
                        <td class="col-level">{last_editor}</td>
                        <td class="col-status"><span class="status-badge unmatched">○ Unmatched</span></td>
                        <td class="col-suggestion">{suggestion}</td>
                </tr>
            """.format(
                area_dept=area_dept,
                area_type=area_type,
                    area_detail=area_detail,
                    area_sf="{:,.0f}".format(float(self._safe_float(area_sf))),
                    creator=creator,
                    last_editor=last_editor,
                    suggestion=suggestion_text
                ))
            
            level_sections.append("""
            <div class="level-section">
                <h4>📍 {level_name} ({area_count} areas, {total_sf:,} SF)</h4>
            <div class="table-container">
                <table class="unmatched-table">
                    <thead>
                        <tr>
                                <th class="col-dept">Department</th>
                                <th class="col-division">Division</th>
                                <th class="col-function">Function</th>
                                <th class="col-area">Area (SF)</th>
                                <th class="col-level">Created By</th>
                                <th class="col-level">Last Edited By</th>
                                <th class="col-status">Status</th>
                                <th class="col-suggestion">Suggested Match</th>
                        </tr>
                    </thead>
                    <tbody>
                            {level_rows}
                    </tbody>
                </table>
            </div>
            </div>
            """.format(
                level_name=level_name.replace('/', ' / '),  # Add spaces around slashes
                area_count=len(level_areas),
                total_sf=int(round(level_total_sf)),  # Round to whole number for readability
                level_rows="".join(level_rows)
            ))
        
        section_title = "○ Unmatched Areas"
        if scheme_name:
            section_title = "{} - {}".format(section_title, scheme_name)
        
        return """
        <div class="unmatched-section">
            <h3>{section_title}</h3>
            <p>The following Revit areas were not matched to any Excel requirements, grouped by level:</p>
            {level_sections}
        </div>
        """.format(
            section_title=section_title,
            level_sections="".join(level_sections)
        )
    
    def _get_status_icon(self, status):
        """Get icon for status"""
        icons = {
            "Fulfilled": "✓",
            "Partial": "△",
            "Missing": "✕",
            "Excessive": "!"
        }
        return icons.get(status, "?")
    
    def _get_css_styles(self):
        """Get CSS styles for the report - High-Tech Minimalist Theme"""
        return """
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        @import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500;700&family=Source+Code+Pro:wght@400;500;600&display=swap');
        
        html, body {
            margin: 0;
            padding: 0;
            width: 100%;
            height: 100%;
        }
        
        body {
            font-family: 'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            line-height: 1.5;
            color: #f8fafc;
            background: #0a0e13;
            min-height: 100vh;
            font-weight: 400;
            position: relative;
        }
        
        .container {
            max-width: 95vw;
            min-width: 1200px;
            margin: 0 auto;
            padding: 24px;
            padding-bottom: 150px; /* Add space for fixed search bar */
            animation: fadeInUp 0.8s ease-out;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(30px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .report-header {
            text-align: center;
            margin-bottom: 48px;
            padding: 40px 32px;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 8px;
            animation: slideInDown 1s ease-out;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .report-header:hover {
            transform: translateY(-2px);
            box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
        }
        
        @keyframes slideInDown {
            from {
                opacity: 0;
                transform: translateY(-50px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }
        
        .report-header h1 {
            color: #ffffff;
            font-size: 2.25rem;
            margin-bottom: 16px;
            font-weight: 600;
            letter-spacing: -0.025em;
        }
        
        .report-info {
            color: #9ca3af;
            font-size: 0.875rem;
            font-weight: 400;
        }
        
        .report-info strong {
            color: #d1d5db;
            font-weight: 500;
        }
        
        .summary-section, .status-summary, .comparison-section, .unmatched-section, .scheme-summary, .scheme-section {
            margin-bottom: 32px;
        }
        
        .summary-section h2, .status-summary h2, .comparison-section h2, .unmatched-section h2, .scheme-summary h2, .scheme-section h2 {
            color: #ffffff;
            margin-bottom: 24px;
            font-size: 1.5rem;
            font-weight: 600;
            letter-spacing: -0.025em;
        }
        
        .unmatched-section h3 {
            color: #f59e0b;
            margin-bottom: 16px;
            font-size: 1.125rem;
            font-weight: 500;
        }
        
        .summary-cards, .scheme-cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        
        .summary-cards .card:nth-child(1) { animation-delay: 0.1s; }
        .summary-cards .card:nth-child(2) { animation-delay: 0.2s; }
        .summary-cards .card:nth-child(3) { animation-delay: 0.3s; }
        .summary-cards .card:nth-child(4) { animation-delay: 0.4s; }
        .summary-cards .card:nth-child(5) { animation-delay: 0.5s; }
        .summary-cards .card:nth-child(6) { animation-delay: 0.6s; }
        .summary-cards .card:nth-child(7) { animation-delay: 0.7s; }
        .summary-cards .card:nth-child(8) { animation-delay: 0.8s; }
        .summary-cards .card:nth-child(9) { animation-delay: 0.9s; }
        
        .card, .scheme-card {
            background: #111827;
            border: 1px solid #1f2937;
            padding: 24px;
            border-radius: 6px;
            text-align: center;
            transition: all 0.3s ease;
            animation: fadeInScale 0.6s ease-out;
        }
        
        .card:hover, .scheme-card:hover {
            transform: translateY(-3px);
            border-color: #4b5563;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.3);
        }
        
        @keyframes fadeInScale {
            from {
                opacity: 0;
                transform: scale(0.95);
            }
            to {
                opacity: 1;
                transform: scale(1);
            }
        }
        
        
        .card h3, .scheme-card h3 {
            font-size: 0.75rem;
            margin-bottom: 8px;
            color: #9ca3af;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 500;
        }
        
        .card-value {
            font-size: 1.875rem;
            font-weight: 600;
            margin-bottom: 4px;
            color: #ffffff;
            font-family: 'Source Code Pro', monospace;
        }
        
        .card-label {
            font-size: 0.75rem;
            color: #6b7280;
            font-weight: 400;
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
            border-radius: 8px;
            background: #111827;
            border: 1px solid #1f2937;
            margin-bottom: 24px;
        }
        
        .comparison-table, .unmatched-table {
            width: 100%;
            border-collapse: collapse;
            border-spacing: 0;
            background-color: transparent;
            font-size: 0.875rem;
            border: 1px solid #374151;
            table-layout: fixed;
        }
        
        .comparison-table th, .unmatched-table th {
            background: #1f2937;
            color: #f9fafb;
            padding: 16px 20px;
            text-align: left;
            font-weight: 600;
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            position: sticky;
            top: 0;
            z-index: 10;
            border: 1px solid #374151;
            border-bottom: 2px solid #4b5563;
            font-family: 'Roboto', sans-serif;
        }
        
        .comparison-table td, .unmatched-table td {
            padding: 16px 20px;
            border: 1px solid #374151;
            color: #e5e7eb;
            font-weight: 400;
            background-color: #111827;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        
        /* Column width classes for responsive design - wider for better readability */
        .col-dept { width: 14%; }
        .col-division { width: 12%; }
        .col-function { width: 14%; }
        .col-level { width: 16%; }
        .col-count { width: 10%; }
        .col-area { width: 12%; }
        .col-delta { width: 14%; }
        .col-status { width: 10%; }
        .col-quality { width: 8%; }
        .col-suggestion { width: 20%; }
        
        /* Add thick division line between Required Area and Level */
        .comparison-table th:nth-child(5),
        .comparison-table td:nth-child(5) {
            border-right: 3px solid #4b5563;
        }
        
        .comparison-table tbody tr, .unmatched-table tbody tr {
            background-color: #111827;
            transition: all 0.3s ease;
            animation: slideInLeft 0.5s ease-out;
        }
        
        .comparison-table tbody tr:nth-child(even), .unmatched-table tbody tr:nth-child(even) {
            animation-delay: 0.1s;
        }
        
        .comparison-table tbody tr:nth-child(odd), .unmatched-table tbody tr:nth-child(odd) {
            animation-delay: 0.05s;
        }
        
        @keyframes slideInLeft {
            from {
                opacity: 0;
                transform: translateX(-20px);
            }
            to {
                opacity: 1;
                transform: translateX(0);
            }
        }
        
        .comparison-table tr:hover td, .unmatched-table tr:hover td {
            background-color: #1f2937;
            border-color: #4b5563;
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
        
        .alert-high-difference {
            background: #7f1d1d !important;
            color: #fecaca !important;
            font-weight: 700;
            border: 2px solid #ef4444 !important;
            animation: alertPulse 2s infinite;
        }
        
        .alert-count-delta {
            background: #78350f !important;
            color: #fed7aa !important;
            font-weight: 700;
            border: 2px solid #f59e0b !important;
        }
        
        .alert-area-delta {
            background: #7c2d12 !important;
            color: #fed7aa !important;
            font-weight: 700;
            border: 2px solid #ea580c !important;
        }
        
        @keyframes alertPulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .status-badge {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.6875rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.025em;
            display: inline-block;
            border: 1px solid transparent;
            transition: all 0.3s ease;
            animation: fadeInScale 0.6s ease-out;
        }
        
        .status-badge:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .status-badge.fulfilled {
            background: #065f46;
            color: #10b981;
            border-color: #10b981;
        }
        
        .status-badge.partial {
            background: #78350f;
            color: #f59e0b;
            border-color: #f59e0b;
        }
        
        .status-badge.missing {
            background: #7f1d1d;
            color: #ef4444;
            border-color: #ef4444;
        }
        
        .status-badge.excessive {
            background: #7c2d12;
            color: #ea580c;
            border-color: #ea580c;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        
        .status-badge.unmatched {
            background: #374151;
            color: #9ca3af;
            border-color: #6b7280;
        }
        
        .quality-badge {
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.625rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.025em;
        }
        
        .quality-badge.high {
            background-color: #0c4a6e;
            color: #38bdf8;
            border: 1px solid #0ea5e9;
        }
        
        .quality-badge.medium {
            background-color: #78350f;
            color: #fbbf24;
            border: 1px solid #f59e0b;
        }
        
        .quality-badge.low, .quality-badge.no {
            background-color: #7f1d1d;
            color: #f87171;
            border: 1px solid #ef4444;
        }
        
        .chart-section {
            margin: 48px 0;
            padding: 32px;
            background: #111827;
            border-radius: 12px;
            border: 1px solid #1f2937;
            text-align: center;
        }
        
        .chart-section h2 {
            color: #ffffff;
            margin-bottom: 24px;
            font-size: 1.5rem;
            font-weight: 600;
        }
        
        .chart-container {
            position: relative;
            width: 100%;
            height: 400px;
            max-width: 500px;
            margin: 0 auto;
        }
        
        .section-diagram {
            margin: 48px 0;
            padding: 32px;
            background: #111827;
            border-radius: 12px;
            border: 1px solid #1f2937;
        }
        
        .section-diagram h2 {
            color: #ffffff;
            margin-bottom: 24px;
            font-size: 1.5rem;
            font-weight: 600;
            text-align: center;
        }
        
        .building-section {
            display: flex;
            justify-content: center;
            align-items: flex-end;
            min-height: 600px;
            padding: 20px;
            position: relative;
        }
        
        .level-stack {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 0 20px;
            position: relative;
        }
        
        .level-label {
            color: #e5e7eb;
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 8px;
            text-align: center;
            min-width: 120px;
        }
        
        .level-elevation {
            color: #9ca3af;
            font-size: 0.75rem;
            margin-bottom: 12px;
        }
        
        .department-pills {
            display: flex;
            flex-direction: column;
            gap: 4px;
            width: 200px;
            min-height: 100px;
        }
        
        .department-pill {
            background: linear-gradient(135deg, var(--dept-color) 0%, var(--dept-color-dark) 100%);
            color: white;
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 500;
            text-align: center;
            border: 1px solid var(--dept-border);
            box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
        }
        
        .department-pill:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.3);
        }
        
        .department-pill::before {
            content: attr(data-area);
            position: absolute;
            top: -20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.65rem;
            opacity: 0;
            transition: opacity 0.3s ease;
            pointer-events: none;
        }
        
        .department-pill:hover::before {
            opacity: 1;
        }
        
        /* Department color variables */
        .dept-emergency { --dept-color: #dc2626; --dept-color-dark: #991b1b; --dept-border: #ef4444; }
        .dept-inpatient { --dept-color: #059669; --dept-color-dark: #047857; --dept-border: #10b981; }
        .dept-diagnostic { --dept-color: #2563eb; --dept-color-dark: #1d4ed8; --dept-border: #3b82f6; }
        .dept-mechanical { --dept-color: #7c3aed; --dept-color-dark: #6d28d9; --dept-border: #8b5cf6; }
        .dept-administration { --dept-color: #ea580c; --dept-color-dark: #c2410c; --dept-border: #f97316; }
        .dept-other { --dept-color: #6b7280; --dept-color-dark: #4b5563; --dept-border: #9ca3af; }
        
        .level-connector {
            position: absolute;
            right: -10px;
            top: 50%;
            transform: translateY(-50%);
            width: 2px;
            height: 100%;
            background: linear-gradient(to bottom, #4b5563, #6b7280, #4b5563);
            opacity: 0.6;
        }
        
        .section-legend {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 16px;
            margin-top: 24px;
            padding: 16px;
            background: #1f2937;
            border-radius: 8px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #e5e7eb;
            font-size: 0.875rem;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            border: 2px solid;
        }
        
        .viewer3d-section {
            margin: 48px 0;
            padding: 32px;
            background: #111827;
            border-radius: 12px;
            border: 1px solid #1f2937;
        }
        
        .viewer3d-section h2 {
            color: #ffffff;
            margin-bottom: 24px;
            font-size: 1.5rem;
            font-weight: 600;
            text-align: center;
        }
        
        .viewer3d-controls {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-bottom: 24px;
            flex-wrap: wrap;
        }
        
        .control-btn {
            padding: 8px 16px;
            background: #1f2937;
            color: #e5e7eb;
            border: 1px solid #374151;
            border-radius: 6px;
            font-size: 0.875rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .control-btn:hover {
            background: #374151;
            border-color: #4b5563;
            transform: translateY(-1px);
        }
        
        .control-btn.active {
            background: #3b82f6;
            border-color: #2563eb;
            color: white;
        }
        
        .viewer3d-container {
            position: relative;
            width: 100%;
            height: 600px;
            background: #0f172a;
            border-radius: 8px;
            border: 1px solid #1f2937;
            overflow: hidden;
        }
        
        #viewer3d-canvas {
            width: 100%;
            height: 100%;
            display: block;
        }
        
        .viewer3d-info {
            position: absolute;
            top: 16px;
            right: 16px;
            z-index: 100;
        }
        
        .info-panel {
            background: rgba(17, 24, 39, 0.95);
            border: 1px solid #374151;
            border-radius: 8px;
            padding: 16px;
            color: #e5e7eb;
            font-size: 0.875rem;
            min-width: 200px;
            backdrop-filter: blur(8px);
        }
        
        .info-panel h4 {
            color: #ffffff;
            margin-bottom: 8px;
            font-size: 1rem;
        }
        
        .viewer3d-legend {
            margin-top: 24px;
            padding: 16px;
            background: #1f2937;
            border-radius: 8px;
        }
        
        .legend-title {
            color: #ffffff;
            font-size: 1rem;
            font-weight: 600;
            margin-bottom: 12px;
            text-align: center;
        }
        
        .legend-items {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 16px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 8px;
            color: #e5e7eb;
            font-size: 0.875rem;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            border: 2px solid;
        }
        
        /* Heatmap colors */
        .heatmap-excellent { background-color: #10b981; border-color: #059669; }
        .heatmap-good { background-color: #84cc16; border-color: #65a30d; }
        .heatmap-fair { background-color: #eab308; border-color: #ca8a04; }
        .heatmap-poor { background-color: #f97316; border-color: #ea580c; }
        .heatmap-critical { background-color: #ef4444; border-color: #dc2626; }
        
        .report-footer {
            text-align: center;
            margin-top: 48px;
            padding: 24px;
            background: #111827;
            border-radius: 8px;
            border: 1px solid #1f2937;
            color: #6b7280;
            font-size: 0.875rem;
        }
        
        .scheme-comparisons {
            display: flex;
            flex-direction: column;
            gap: 24px;
        }
        
        .scheme-section {
            background: #111827;
            padding: 24px;
            border-radius: 8px;
            border: 1px solid #1f2937;
        }
        
        @media (max-width: 768px) {
            .container {
                padding: 15px 10px;
            }
            
            .comparison-table, .unmatched-table {
                font-size: 0.75rem;
            }
            
            .comparison-table th, .unmatched-table th,
            .comparison-table td, .unmatched-table td {
                padding: 8px 6px;
            }
            
            /* Adjust column widths for mobile */
            .col-dept { width: 15%; }
            .col-division { width: 12%; }
            .col-function { width: 15%; }
            .col-level { width: 15%; }
            .col-count { width: 10%; }
            .col-area { width: 12%; }
            .col-delta { width: 15%; }
            .col-status { width: 6%; }
        }
        
        @media (max-width: 480px) {
            .comparison-table, .unmatched-table {
                font-size: 0.7rem;
            }
            
            .comparison-table th, .unmatched-table th,
            .comparison-table td, .unmatched-table td {
                padding: 6px 4px;
            }
            
            /* Further adjust for very small screens */
            .col-dept { width: 18%; }
            .col-division { width: 15%; }
            .col-function { width: 18%; }
            .col-level { width: 18%; }
            .col-count { width: 12%; }
            .col-area { width: 15%; }
            .col-delta { width: 18%; }
            .col-status { width: 8%; }
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
        
        /* Sticky Search Bar at Bottom - Floating Element */
        .search-bar-container {
            position: fixed !important;
            bottom: 0 !important;
            left: 0 !important;
            right: 0 !important;
            width: 100%;
            background: linear-gradient(180deg, rgba(10, 14, 19, 0) 0%, rgba(10, 14, 19, 0.8) 15%, #0a0e13 30%);
            padding: 24px 0 16px 0;
            z-index: 10000;
            box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(8px);
            pointer-events: auto;
        }
        
        .search-bar-content {
            max-width: 95vw;
            margin: 0 auto;
            padding: 0 24px 16px 24px;
            position: relative;
        }
        
        #fuzzySearch {
            width: 100%;
            padding: 14px 20px;
            background: #111827;
            border: 2px solid #1f2937;
            border-radius: 8px;
            color: #f8fafc;
            font-size: 1rem;
            font-family: 'Roboto', sans-serif;
            outline: none;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        #fuzzySearch:focus {
            border-color: #60a5fa;
            box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.2);
        }
        
        #fuzzySearch::placeholder {
            color: #6b7280;
        }
        
        .clear-search-btn {
            position: absolute;
            right: 12px;
            top: 50%;
            transform: translateY(-50%);
            background: #374151;
            border: none;
            color: #f8fafc;
            width: 32px;
            height: 32px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1.2rem;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .clear-search-btn:hover {
            background: #60a5fa;
            transform: translateY(-50%) scale(1.1);
        }
        
        .search-status {
            position: absolute;
            bottom: 100%;
            left: 0;
            right: 0;
            margin-bottom: 8px;
            padding: 8px 12px;
            background: #1f2937;
            border: 1px solid #374151;
            border-radius: 6px;
            color: #9ca3af;
            font-size: 0.875rem;
            display: none;
            box-shadow: 0 -4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .search-status.active {
            display: block;
        }
        
        .search-status .count {
            color: #60a5fa;
            font-weight: 600;
        }
        
        /* Department collapse styles */
        .dept-row.collapsed {
            display: none;
        }
        
        .department-header.collapsed .collapse-icon {
            transform: rotate(-90deg);
        }
        
        /* Search filter styles */
        .dept-row.search-hidden {
            display: none !important;
        }
        
        .department-header.search-hidden {
            display: none !important;
        }
        
        /* Suggestion column styles */
        .suggestion-text {
            color: #9ca3af;
            font-size: 0.9rem;
            font-style: italic;
        }
        
        .suggestion-text strong {
            color: #60a5fa;
            font-weight: 600;
            font-style: normal;
        }
        
        /* Context Menu Styles */
        .context-menu {
            position: fixed;
            background: #1f2937;
            border: 2px solid #374151;
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
            z-index: 9999;
            min-width: 220px;
            display: none;
            overflow: hidden;
        }
        
        .context-menu.active {
            display: block;
        }
        
        .context-menu-item {
            padding: 12px 16px;
            color: #f8fafc;
            cursor: pointer;
            transition: background 0.2s ease;
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 0.95rem;
            border-bottom: 1px solid #374151;
        }
        
        .context-menu-item:last-child {
            border-bottom: none;
        }
        
        .context-menu-item:hover {
            background: #374151;
        }
        
        .context-menu-icon {
            font-size: 1.1rem;
            color: #60a5fa;
            width: 20px;
            text-align: center;
        }
        
        /* Minimap Navigation Styles */
        .minimap-nav {
            position: fixed;
            right: 24px;
            top: 50%;
            transform: translateY(-50%);
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 8px;
            padding: 16px 12px;
            z-index: 998;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.6);
            max-height: 80vh;
            overflow-y: auto;
            min-width: 200px;
            transition: all 0.3s ease;
        }
        
        .minimap-nav:hover {
            border-color: #374151;
            box-shadow: 0 12px 50px rgba(0, 0, 0, 0.7);
        }
        
        .minimap-title {
            color: #9ca3af;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #1f2937;
            text-align: center;
        }
        
        .minimap-item {
            display: flex;
            align-items: center;
            padding: 8px 12px;
            margin: 4px 0;
            color: #9ca3af;
            font-size: 0.8rem;
            cursor: pointer;
            border-radius: 6px;
            transition: all 0.2s ease;
            border-left: 3px solid transparent;
            position: relative;
        }
        
        .minimap-item:hover {
            background: #1f2937;
            color: #f8fafc;
            border-left-color: #60a5fa;
            transform: translateX(-2px);
        }
        
        .minimap-item.active {
            background: #1f2937;
            color: #60a5fa;
            border-left-color: #60a5fa;
            font-weight: 600;
        }
        
        .minimap-item.active::before {
            content: '';
            position: absolute;
            left: -12px;
            top: 50%;
            transform: translateY(-50%);
            width: 8px;
            height: 8px;
            background: #60a5fa;
            border-radius: 50%;
            box-shadow: 0 0 8px rgba(96, 165, 250, 0.6);
        }
        
        .minimap-icon {
            margin-right: 8px;
            font-size: 1rem;
            min-width: 16px;
            text-align: center;
        }
        
        .minimap-toggle {
            position: fixed;
            right: 24px;
            top: 24px;
            background: #111827;
            border: 1px solid #1f2937;
            border-radius: 6px;
            padding: 8px 12px;
            color: #9ca3af;
            cursor: pointer;
            z-index: 999;
            font-size: 0.875rem;
            transition: all 0.3s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .minimap-toggle:hover {
            background: #1f2937;
            color: #60a5fa;
            border-color: #374151;
        }
        
        .minimap-nav.hidden {
            opacity: 0;
            pointer-events: none;
            transform: translateY(-50%) translateX(20px);
        }
        
        /* Scrollbar styling for minimap */
        .minimap-nav::-webkit-scrollbar {
            width: 6px;
        }
        
        .minimap-nav::-webkit-scrollbar-track {
            background: #0a0e13;
            border-radius: 3px;
        }
        
        .minimap-nav::-webkit-scrollbar-thumb {
            background: #374151;
            border-radius: 3px;
        }
        
        .minimap-nav::-webkit-scrollbar-thumb:hover {
            background: #4b5563;
        }
        """
    
    def _get_javascript(self):
        """Get JavaScript for interactive features"""
        return """
        // Load Chart.js and Three.js from CDN
        const chartScript = document.createElement('script');
        chartScript.src = 'https://cdn.jsdelivr.net/npm/chart.js';
        chartScript.onload = function() {
            initializeChart();
        };
        document.head.appendChild(chartScript);
        
        // Load Three.js
        const threeScript = document.createElement('script');
        threeScript.src = 'https://cdn.jsdelivr.net/npm/three@0.158.0/build/three.min.js';
        threeScript.onload = function() {
            const controlsScript = document.createElement('script');
            controlsScript.src = 'https://cdn.jsdelivr.net/npm/three@0.158.0/examples/js/controls/OrbitControls.js';
            controlsScript.onload = function() {
                initialize3DViewer();
            };
            document.head.appendChild(controlsScript);
        };
        document.head.appendChild(threeScript);
        
        function initializeChart() {
            console.log('initializeChart called');
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
                    initializeComponents();
                });
            } else {
                initializeComponents();
            }
        }
        
        function initializeComponents() {
            console.log('Initializing components...');
            
            // Initialize fuzzy search
            initializeFuzzySearch();
            
            // Initialize context menu
            initializeContextMenu();
            
            // Table sorting disabled per user request
            // const table = document.querySelector('.comparison-table');
            // if (table) {
            //     console.log('Found comparison table, adding sorting...');
            //     const headers = table.querySelectorAll('th');
            //     headers.forEach((header, index) => {
            //         header.style.cursor = 'pointer';
            //         header.addEventListener('click', () => {
            //             sortTable(table, index);
            //         });
            //     });
            // } else {
            //     console.log('No comparison table found');
            // }
            
            // Initialize donut chart if canvas exists
            const ctx = document.getElementById('areaFulfillmentChart');
            if (ctx && typeof Chart !== 'undefined') {
                console.log('Creating donut chart...');
                createDonutChart(ctx);
            } else {
                console.log('Chart canvas or Chart.js not available');
            }
            
            // Initialize department charts
            initializeDepartmentCharts();
            
            // Initialize building section diagram
            console.log('Creating building section...');
            createBuildingSection();
        }
        
        function initializeDepartmentCharts() {
            console.log('Initializing department charts...');
            
            // Get chart data from script tag
            const chartDataElement = document.getElementById('departmentChartData');
            if (!chartDataElement) {
                console.log('No department chart data found');
                return;
            }
            
            const chartData = JSON.parse(chartDataElement.textContent);
            console.log('Department chart data:', chartData);
            
            // Create comparison chart
            const comparisonCanvas = document.getElementById('deptComparisonChart');
            if (comparisonCanvas) {
                createDepartmentComparisonChart(comparisonCanvas, chartData);
            }
            
            // Create percentage chart
            const percentageCanvas = document.getElementById('deptPercentageChart');
            if (percentageCanvas) {
                createDepartmentPercentageChart(percentageCanvas, chartData);
            }
        }
        
        function createDepartmentComparisonChart(canvas, data) {
            console.log('Creating department comparison chart...');
            
            new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: data.departments,
                    datasets: [
                        {
                            label: 'Target DGSF',
                            data: data.target_dgsf,
                            backgroundColor: data.colors.map(c => c + '40'),
                            borderColor: data.colors,
                            borderWidth: 2,
                            borderRadius: 6,
                            borderSkipped: false
                        },
                        {
                            label: 'Actual DGSF',
                            data: data.actual_dgsf,
                            backgroundColor: data.colors.map(c => c + '80'),
                            borderColor: data.colors,
                            borderWidth: 2,
                            borderRadius: 6,
                            borderSkipped: false
                        }
                    ]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: true,
                            position: 'top',
                            labels: {
                                color: '#e5e7eb',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 14
                                },
                                padding: 16,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1f2937',
                            titleColor: '#f9fafb',
                            bodyColor: '#e5e7eb',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            displayColors: true,
                            callbacks: {
                                label: function(context) {
                                    const label = context.dataset.label || '';
                                    const value = context.parsed.x;
                                    return label + ': ' + value.toLocaleString() + ' SF';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            stacked: false,
                            grid: {
                                color: '#374151',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#9ca3af',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 11
                                },
                                callback: function(value) {
                                    return value.toLocaleString();
                                }
                            },
                            title: {
                                display: true,
                                text: 'Square Feet (SF)',
                                color: '#9ca3af',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 12,
                                    weight: '500'
                                }
                            }
                        },
                        y: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#e5e7eb',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 14,
                                    weight: '400'
                                }
                            }
                        }
                    },
                    animation: {
                        duration: 1500,
                        easing: 'easeInOutQuart'
                    }
                }
            });
        }
        
        function createDepartmentPercentageChart(canvas, data) {
            console.log('Creating department percentage chart...');
            
            // Color code based on percentage
            const barColors = data.percentages.map(pct => {
                if (Math.abs(pct) <= 5) return '#10b981'; // Green - on target
                if (pct > 5) return '#f59e0b'; // Orange - over
                return '#ef4444'; // Red - under
            });
            
            new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: data.departments,
                    datasets: [{
                        label: 'Fulfillment %',
                        data: data.percentages,
                        backgroundColor: barColors.map(c => c + '80'),
                        borderColor: barColors,
                        borderWidth: 2,
                        borderRadius: 6,
                        borderSkipped: false
                    }]
                },
                options: {
                    indexAxis: 'y',
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        },
                        tooltip: {
                            backgroundColor: '#1f2937',
                            titleColor: '#f9fafb',
                            bodyColor: '#e5e7eb',
                            borderColor: '#374151',
                            borderWidth: 1,
                            padding: 12,
                            callbacks: {
                                label: function(context) {
                                    const value = context.parsed.x;
                                    const status = Math.abs(value) <= 5 ? 'On Target' : 
                                                   value > 5 ? 'Over' : 'Under';
                                    return status + ': ' + (value > 0 ? '+' : '') + value.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            grid: {
                                color: '#374151',
                                drawBorder: false
                            },
                            ticks: {
                                color: '#9ca3af',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 11
                                },
                                callback: function(value) {
                                    return (value > 0 ? '+' : '') + value + '%';
                                }
                            },
                            title: {
                                display: true,
                                text: 'Percentage Difference',
                                color: '#9ca3af',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 12,
                                    weight: '500'
                                }
                            }
                        },
                        y: {
                            grid: {
                                display: false
                            },
                            ticks: {
                                color: '#e5e7eb',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 14,
                                    weight: '400'
                                }
                            }
                        }
                    },
                    animation: {
                        duration: 1500,
                        easing: 'easeInOutQuart'
                    }
                }
            });
        }
        
        function initialize3DViewer() {
            console.log('initialize3DViewer called');
            // Wait for DOM to be ready
            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', function() {
                    initialize3DComponents();
                });
            } else {
                initialize3DComponents();
            }
        }
        
        function initialize3DComponents() {
            console.log('Initializing 3D components...');
            const canvas = document.getElementById('viewer3d-canvas');
            if (canvas && typeof THREE !== 'undefined') {
                console.log('Creating 3D viewer...');
                create3DViewer(canvas);
            } else {
                console.log('3D canvas or Three.js not available');
            }
        }
        
        function createDonutChart(canvas) {
            console.log('Creating donut chart...');
            
            // Calculate data from the table rows
            let fulfilledArea = 0;
            let totalRequiredArea = 0;
            let mismatchedArea = 0;
            let missingArea = 0;
            
            // Extract data from table rows
            const tableRows = document.querySelectorAll('.comparison-table tbody tr');
            console.log('Found table rows for chart:', tableRows.length);
            
            if (tableRows.length === 0) {
                console.log('No table rows found, using demo data');
                // Use demo data
                fulfilledArea = 750000;
                totalRequiredArea = 1000000;
                mismatchedArea = 150000;
                missingArea = 100000;
            } else {
            tableRows.forEach(row => {
                const cells = row.cells;
                if (cells.length >= 8) {
                    const requiredArea = parseFloat(cells[5].textContent.replace(/[^0-9.-]/g, '')) || 0;
                    const actualArea = parseFloat(cells[7].textContent.replace(/[^0-9.-]/g, '')) || 0;
                    const status = cells[12].textContent.trim();
                    
                    totalRequiredArea += requiredArea;
                    
                    if (status.includes('Fulfilled')) {
                        fulfilledArea += actualArea;
                    } else if (status.includes('Partial') || status.includes('Excessive')) {
                        mismatchedArea += actualArea;
                    } else if (status.includes('Missing')) {
                        missingArea += requiredArea; // Missing areas count as required area
                    }
                }
            });
            }
            
            // Calculate percentages
            const totalArea = Math.max(totalRequiredArea, fulfilledArea + mismatchedArea);
            const fulfilledPercentage = totalArea > 0 ? (fulfilledArea / totalArea * 100) : 0;
            const mismatchedPercentage = totalArea > 0 ? (mismatchedArea / totalArea * 100) : 0;
            const missingPercentage = totalArea > 0 ? (missingArea / totalArea * 100) : 0;
            
            new Chart(canvas, {
                type: 'doughnut',
                data: {
                    labels: ['Fulfilled Areas', 'Mismatched Areas', 'Missing Areas'],
                    datasets: [{
                        data: [fulfilledPercentage, mismatchedPercentage, missingPercentage],
                        backgroundColor: [
                            '#10b981',  // Green for fulfilled
                            '#f59e0b',  // Orange for mismatched  
                            '#ef4444'   // Red for missing
                        ],
                        borderColor: [
                            '#059669',
                            '#d97706',
                            '#dc2626'
                        ],
                        borderWidth: 2,
                        hoverOffset: 8
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'bottom',
                            labels: {
                                color: '#e5e7eb',
                                font: {
                                    family: "'Roboto', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    size: 14
                                },
                                padding: 20,
                                usePointStyle: true
                            }
                        },
                        tooltip: {
                            backgroundColor: '#1f2937',
                            titleColor: '#f9fafb',
                            bodyColor: '#e5e7eb',
                            borderColor: '#374151',
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    const label = context.label || '';
                                    const value = context.parsed;
                                    return label + ': ' + value.toFixed(1) + '%';
                                }
                            }
                        }
                    },
                    cutout: '60%',
                    animation: {
                        animateRotate: true,
                        animateScale: true,
                        duration: 2000,
                        easing: 'easeOutQuart'
                    }
                }
            });
        }
        
        function createBuildingSection() {
            const buildingSection = document.getElementById('buildingSection');
            const sectionLegend = document.getElementById('sectionLegend');
            
            if (!buildingSection) {
                console.log('Building section element not found');
                return;
            }
            
            console.log('Creating building section diagram...');
            
            // Debug: Check if table exists
            const table = document.querySelector('.comparison-table');
            if (!table) {
                console.log('Comparison table not found, showing demo content');
                showDemoBuildingSection(buildingSection, sectionLegend);
                return;
            }
            
            // Extract level and department data from table
            const levelData = {};
            const departmentColors = {
                'EMERGENCY': 'dept-emergency',
                'INPATIENT CARE': 'dept-inpatient',
                'DIAGNOSTIC AND TREATMENT': 'dept-diagnostic',
                'MECHANICAL': 'dept-mechanical',
                'ADMINISTRATION AND STAFF SUPPORT': 'dept-administration'
            };
            
            const tableRows = document.querySelectorAll('.comparison-table tbody tr');
            console.log('Found table rows:', tableRows.length);
            
            if (tableRows.length === 0) {
                buildingSection.innerHTML = '<p style="color: #9ca3af; text-align: center; padding: 40px;">No data rows found in comparison table.</p>';
                return;
            }
            
            tableRows.forEach((row, rowIndex) => {
                const cells = row.cells;
                console.log(`Row ${rowIndex}: ${cells.length} cells`);
                
                if (cells.length >= 8) {
                    const department = cells[0].textContent.trim(); // Department column
                    const levelText = cells[5].textContent.trim(); // Level column (moved to position 5)
                    const actualArea = parseFloat(cells[7].textContent.replace(/[^0-9.-]/g, '')) || 0; // Actual Area column
                    
                    console.log(`Row ${rowIndex}: Dept=${department}, Level=${levelText}, Area=${actualArea}`);
                    
                    // Extract level name and elevation from level text
                    const levelMatch = levelText.match(/(Level \d+)/);
                    if (levelMatch) {
                        const levelName = levelMatch[1];
                        
                        if (!levelData[levelName]) {
                            levelData[levelName] = {};
                        }
                        
                        if (!levelData[levelName][department]) {
                            levelData[levelName][department] = 0;
                        }
                        
                        levelData[levelName][department] += actualArea;
                    }
                }
            });
            
            console.log('Extracted level data:', levelData);
            
            // Sort levels by elevation (assuming Level 1, Level 2, etc.)
            const sortedLevels = Object.keys(levelData).sort((a, b) => {
                const aNum = parseInt(a.match(/\d+/)[0]);
                const bNum = parseInt(b.match(/\d+/)[0]);
                return aNum - bNum;
            });
            
            console.log('Sorted levels:', sortedLevels);
            
            // Generate level stacks
            let sectionHTML = '';
            let legendHTML = '';
            const usedDepartments = new Set();
            
            if (sortedLevels.length === 0) {
                buildingSection.innerHTML = '<p style="color: #9ca3af; text-align: center; padding: 40px;">No level data found. Please check that areas have level information.</p>';
                return;
            }
            
            sortedLevels.forEach((levelName, index) => {
                const departments = levelData[levelName];
                const levelNum = levelName.match(/\d+/)[0];
                const elevation = (parseInt(levelNum) * 10).toFixed(1); // Approximate elevation
                
                let pillsHTML = '';
                Object.entries(departments).forEach(([dept, area]) => {
                    if (area > 0) {
                        const deptClass = departmentColors[dept.toUpperCase()] || 'dept-other';
                        const areaSF = Math.round(area).toLocaleString();
                        pillsHTML += `<div class="department-pill ${deptClass}" data-area="${areaSF} SF">${dept}</div>`;
                        usedDepartments.add(dept);
                    }
                });
                
                if (pillsHTML) {
                    sectionHTML += `
                        <div class="level-stack">
                            <div class="level-label">${levelName}</div>
                            <div class="level-elevation">${elevation}'</div>
                            <div class="department-pills">${pillsHTML}</div>
                            ${index < sortedLevels.length - 1 ? '<div class="level-connector"></div>' : ''}
                        </div>
                    `;
                }
            });
            
            // Generate legend
            usedDepartments.forEach(dept => {
                const deptClass = departmentColors[dept.toUpperCase()] || 'dept-other';
                legendHTML += `
                    <div class="legend-item">
                        <div class="legend-color ${deptClass}"></div>
                        <span>${dept}</span>
                    </div>
                `;
            });
            
            if (sectionHTML === '') {
                // Fallback: Create a simple demo diagram
                sectionHTML = `
                    <div class="level-stack">
                        <div class="level-label">Level 1</div>
                        <div class="level-elevation">10.0'</div>
                        <div class="department-pills">
                            <div class="department-pill dept-emergency" data-area="2,500 SF">Emergency</div>
                            <div class="department-pill dept-administration" data-area="1,200 SF">Administration</div>
                        </div>
                    </div>
                    <div class="level-connector"></div>
                    <div class="level-stack">
                        <div class="level-label">Level 2</div>
                        <div class="level-elevation">20.0'</div>
                        <div class="department-pills">
                            <div class="department-pill dept-inpatient" data-area="15,000 SF">Inpatient Care</div>
                            <div class="department-pill dept-diagnostic" data-area="8,500 SF">Diagnostic & Treatment</div>
                        </div>
                    </div>
                    <div class="level-connector"></div>
                    <div class="level-stack">
                        <div class="level-label">Level 3</div>
                        <div class="level-elevation">30.0'</div>
                        <div class="department-pills">
                            <div class="department-pill dept-mechanical" data-area="3,200 SF">Mechanical</div>
                        </div>
                    </div>
                `;
                legendHTML = `
                    <div class="legend-item">
                        <div class="legend-color dept-emergency"></div>
                        <span>Emergency</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color dept-administration"></div>
                        <span>Administration</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color dept-inpatient"></div>
                        <span>Inpatient Care</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color dept-diagnostic"></div>
                        <span>Diagnostic & Treatment</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color dept-mechanical"></div>
                        <span>Mechanical</span>
                    </div>
                `;
            }
            
            buildingSection.innerHTML = sectionHTML;
            sectionLegend.innerHTML = legendHTML;
        }
        
        function showDemoBuildingSection(buildingSection, sectionLegend) {
            console.log('Showing demo building section');
            const demoHTML = `
                <div class="level-stack">
                    <div class="level-label">Level 1</div>
                    <div class="level-elevation">10.0'</div>
                    <div class="department-pills">
                        <div class="department-pill dept-emergency" data-area="2,500 SF">Emergency</div>
                        <div class="department-pill dept-administration" data-area="1,200 SF">Administration</div>
                    </div>
                </div>
                <div class="level-connector"></div>
                <div class="level-stack">
                    <div class="level-label">Level 2</div>
                    <div class="level-elevation">20.0'</div>
                    <div class="department-pills">
                        <div class="department-pill dept-inpatient" data-area="15,000 SF">Inpatient Care</div>
                        <div class="department-pill dept-diagnostic" data-area="8,500 SF">Diagnostic & Treatment</div>
                    </div>
                </div>
                <div class="level-connector"></div>
                <div class="level-stack">
                    <div class="level-label">Level 3</div>
                    <div class="level-elevation">30.0'</div>
                    <div class="department-pills">
                        <div class="department-pill dept-mechanical" data-area="3,200 SF">Mechanical</div>
                    </div>
                </div>
            `;
            
            const demoLegend = `
                <div class="legend-item">
                    <div class="legend-color dept-emergency"></div>
                    <span>Emergency</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color dept-administration"></div>
                    <span>Administration</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color dept-inpatient"></div>
                    <span>Inpatient Care</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color dept-diagnostic"></div>
                    <span>Diagnostic & Treatment</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color dept-mechanical"></div>
                    <span>Mechanical</span>
                </div>
            `;
            
            buildingSection.innerHTML = demoHTML;
            sectionLegend.innerHTML = demoLegend;
        }
        
        function create3DViewer(canvas) {
            console.log('Initializing 3D viewer...');
            
            if (typeof THREE === 'undefined') {
                console.error('Three.js not loaded');
                canvas.parentElement.innerHTML = '<p style="color: #ef4444; text-align: center; padding: 40px;">Three.js library failed to load. Please refresh the page.</p>';
                return;
            }
            
            // Scene setup
            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x0f172a);
            
            // Camera setup
            const camera = new THREE.PerspectiveCamera(75, canvas.clientWidth / canvas.clientHeight, 0.1, 1000);
            camera.position.set(50, 50, 50);
            
            // Renderer setup
            const renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true });
            renderer.setSize(canvas.clientWidth, canvas.clientHeight);
            renderer.shadowMap.enabled = true;
            renderer.shadowMap.type = THREE.PCFSoftShadowMap;
            
            // Controls
            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.enableZoom = true;
            controls.enablePan = true;
            
            // Lighting
            const ambientLight = new THREE.AmbientLight(0x404040, 0.6);
            scene.add(ambientLight);
            
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(50, 100, 50);
            directionalLight.castShadow = true;
            directionalLight.shadow.mapSize.width = 2048;
            directionalLight.shadow.mapSize.height = 2048;
            scene.add(directionalLight);
            
            // Extract data from table
            const buildingData = extractBuildingData();
            
            // Create building geometry
            createBuildingGeometry(scene, buildingData);
            
            // Setup controls
            setup3DControls(controls, scene, camera, renderer);
            
            // Animation loop
            function animate() {
                requestAnimationFrame(animate);
                controls.update();
                renderer.render(scene, camera);
            }
            animate();
            
            // Handle window resize
            window.addEventListener('resize', function() {
                const width = canvas.clientWidth;
                const height = canvas.clientHeight;
                camera.aspect = width / height;
                camera.updateProjectionMatrix();
                renderer.setSize(width, height);
            });
        }
        
        function extractBuildingData() {
            console.log('Extracting building data for 3D viewer...');
            const levelData = {};
            const tableRows = document.querySelectorAll('.comparison-table tbody tr');
            
            console.log('Found table rows for 3D:', tableRows.length);
            
            if (tableRows.length === 0) {
                console.log('No table rows found, creating demo data');
                // Create demo data for 3D viewer
                return {
                    'Level 1': {
                        level: 1,
                        elevation: 10,
                        departments: {
                            'Emergency': { requiredArea: 2500, actualArea: 2500, status: 'Fulfilled' },
                            'Administration': { requiredArea: 1200, actualArea: 1200, status: 'Fulfilled' }
                        }
                    },
                    'Level 2': {
                        level: 2,
                        elevation: 20,
                        departments: {
                            'Inpatient Care': { requiredArea: 15000, actualArea: 18000, status: 'Excessive' },
                            'Diagnostic & Treatment': { requiredArea: 8500, actualArea: 7500, status: 'Partial' }
                        }
                    },
                    'Level 3': {
                        level: 3,
                        elevation: 30,
                        departments: {
                            'Mechanical': { requiredArea: 3200, actualArea: 3200, status: 'Fulfilled' }
                        }
                    }
                };
            }
            
            tableRows.forEach(row => {
                const cells = row.cells;
                if (cells.length >= 8) {
                    const department = cells[0].textContent.trim();
                    const levelText = cells[5].textContent.trim();
                    const requiredArea = parseFloat(cells[4].textContent.replace(/[^0-9.-]/g, '')) || 0;
                    const actualArea = parseFloat(cells[7].textContent.replace(/[^0-9.-]/g, '')) || 0;
                    const status = cells[12].textContent.trim();
                    
                    const levelMatch = levelText.match(/(Level \d+)/);
                    if (levelMatch) {
                        const levelName = levelMatch[1];
                        const levelNum = parseInt(levelName.match(/\d+/)[0]);
                        
                        if (!levelData[levelName]) {
                            levelData[levelName] = {
                                level: levelNum,
                                elevation: levelNum * 10,
                                departments: {}
                            };
                        }
                        
                        if (!levelData[levelName].departments[department]) {
                            levelData[levelName].departments[department] = {
                                requiredArea: 0,
                                actualArea: 0,
                                status: status
                            };
                        }
                        
                        levelData[levelName].departments[department].requiredArea += requiredArea;
                        levelData[levelName].departments[department].actualArea += actualArea;
                    }
                }
            });
            
            console.log('Extracted 3D building data:', levelData);
            return levelData;
        }
        
        function createBuildingGeometry(scene, buildingData) {
            const levels = Object.keys(buildingData).sort((a, b) => {
                return buildingData[a].level - buildingData[b].level;
            });
            
            levels.forEach((levelName, levelIndex) => {
                const levelInfo = buildingData[levelName];
                const elevation = levelInfo.elevation;
                
                // Create floor plane
                const floorGeometry = new THREE.PlaneGeometry(100, 100);
                const floorMaterial = new THREE.MeshLambertMaterial({ 
                    color: 0x374151,
                    transparent: true,
                    opacity: 0.3
                });
                const floor = new THREE.Mesh(floorGeometry, floorMaterial);
                floor.rotation.x = -Math.PI / 2;
                floor.position.y = elevation;
                scene.add(floor);
                
                // Create department zones
                const departments = Object.keys(levelInfo.departments);
                departments.forEach((dept, deptIndex) => {
                    const deptData = levelInfo.departments[dept];
                    const compliance = calculateCompliance(deptData.actualArea, deptData.requiredArea);
                    const color = getComplianceColor(compliance);
                    
                    // Create department box
                    const boxGeometry = new THREE.BoxGeometry(20, 5, 20);
                    const boxMaterial = new THREE.MeshLambertMaterial({ 
                        color: color,
                        transparent: true,
                        opacity: 0.8
                    });
                    const box = new THREE.Mesh(boxGeometry, boxMaterial);
                    
                    // Position boxes in a grid
                    const x = (deptIndex % 5 - 2) * 22;
                    const z = Math.floor(deptIndex / 5) * 22 - 22;
                    box.position.set(x, elevation + 2.5, z);
                    
                    // Add department label
                    const textGeometry = new THREE.PlaneGeometry(18, 3);
                    const textMaterial = new THREE.MeshBasicMaterial({ 
                        color: 0xffffff,
                        transparent: true,
                        opacity: 0.9
                    });
                    const textMesh = new THREE.Mesh(textGeometry, textMaterial);
                    textMesh.position.set(x, elevation + 6, z);
                    scene.add(textMesh);
                    
                    // Store metadata
                    box.userData = {
                        department: dept,
                        level: levelName,
                        compliance: compliance,
                        requiredArea: deptData.requiredArea,
                        actualArea: deptData.actualArea
                    };
                    
                    scene.add(box);
                });
            });
        }
        
        function calculateCompliance(actual, required) {
            if (required === 0) return 0;
            return Math.min(actual / required, 1.5); // Cap at 150% for visualization
        }
        
        function getComplianceColor(compliance) {
            if (compliance >= 0.9) return 0x10b981; // Green - Excellent
            if (compliance >= 0.7) return 0x84cc16; // Light Green - Good
            if (compliance >= 0.5) return 0xeab308; // Yellow - Fair
            if (compliance >= 0.3) return 0xf97316; // Orange - Poor
            return 0xef4444; // Red - Critical
        }
        
        function setup3DControls(controls, scene, camera, renderer) {
            // Control button handlers
            const controlButtons = document.querySelectorAll('.control-btn');
            controlButtons.forEach(btn => {
                btn.addEventListener('click', function() {
                    // Remove active class from all buttons
                    controlButtons.forEach(b => b.classList.remove('active'));
                    // Add active class to clicked button
                    this.classList.add('active');
                    
                    const mode = this.dataset.mode;
                    switch(mode) {
                        case 'compliance':
                            updateHeatmapMode(scene, 'compliance');
                            break;
                        case 'departments':
                            updateHeatmapMode(scene, 'departments');
                            break;
                        case 'areas':
                            updateHeatmapMode(scene, 'areas');
                            break;
                        case 'reset':
                            resetCameraView(controls, camera);
                            break;
                    }
                });
            });
            
            // Click handler for object selection
            const raycaster = new THREE.Raycaster();
            const mouse = new THREE.Vector2();
            
            renderer.domElement.addEventListener('click', function(event) {
                const rect = renderer.domElement.getBoundingClientRect();
                mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
                mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
                
                raycaster.setFromCamera(mouse, camera);
                const intersects = raycaster.intersectObjects(scene.children, true);
                
                if (intersects.length > 0) {
                    const object = intersects[0].object;
                    if (object.userData && object.userData.department) {
                        showObjectInfo(object.userData);
                    }
                }
            });
        }
        
        function updateHeatmapMode(scene, mode) {
            // Update legend
            const legendItems = document.getElementById('viewer3d-legend');
            let legendHTML = '';
            
            if (mode === 'compliance') {
                legendHTML = `
                    <div class="legend-item">
                        <div class="legend-color heatmap-excellent"></div>
                        <span>Excellent (90%+)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color heatmap-good"></div>
                        <span>Good (70-89%)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color heatmap-fair"></div>
                        <span>Fair (50-69%)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color heatmap-poor"></div>
                        <span>Poor (30-49%)</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color heatmap-critical"></div>
                        <span>Critical (<30%)</span>
                    </div>
                `;
            } else if (mode === 'departments') {
                // Department color legend would go here
                legendHTML = `<div class="legend-item"><span>Department View Mode</span></div>`;
            } else if (mode === 'areas') {
                legendHTML = `<div class="legend-item"><span>Area Density View Mode</span></div>`;
            }
            
            legendItems.innerHTML = legendHTML;
        }
        
        function resetCameraView(controls, camera) {
            camera.position.set(50, 50, 50);
            controls.target.set(0, 0, 0);
            controls.update();
        }
        
        function showObjectInfo(userData) {
            const infoPanel = document.querySelector('.info-panel');
            infoPanel.innerHTML = `
                <h4>${userData.department}</h4>
                <p><strong>Level:</strong> ${userData.level}</p>
                <p><strong>Required Area:</strong> ${userData.requiredArea.toLocaleString()} SF</p>
                <p><strong>Actual Area:</strong> ${userData.actualArea.toLocaleString()} SF</p>
                <p><strong>Compliance:</strong> ${(userData.compliance * 100).toFixed(1)}%</p>
            `;
        }
        
        // Toggle department collapse
        function toggleDepartment(deptId) {
            const deptRows = document.querySelectorAll('.dept-row[data-dept="' + deptId + '"]');
            const deptHeader = document.querySelector('.department-header[data-dept-id="' + deptId + '"]');
            const icon = document.getElementById('icon_' + deptId);
            
            deptRows.forEach(row => {
                row.classList.toggle('collapsed');
            });
            
            deptHeader.classList.toggle('collapsed');
        }
        
        // Fuzzy search filter initialization
        let fuseInstance = null;
        let searchData = [];
        
        function initializeFuzzySearch() {
            console.log('Initializing fuzzy search filter...');
            
            // Collect all searchable items from table
            const rows = document.querySelectorAll('.dept-row');
            searchData = Array.from(rows).map(row => ({
                element: row,
                department: row.getAttribute('data-search-dept') || '',
                division: row.getAttribute('data-search-division') || '',
                function: row.getAttribute('data-search-function') || ''
            }));
            
            // Initialize Fuse.js with fuzzy search options
            const fuseOptions = {
                keys: [
                    { name: 'department', weight: 0.4 },
                    { name: 'division', weight: 0.3 },
                    { name: 'function', weight: 0.3 }
                ],
                threshold: 0.4, // More lenient matching (0.0 = exact, 1.0 = match anything)
                distance: 100, // Maximum distance for matching
                ignoreLocation: true, // Don't care about position of match
                useExtendedSearch: false,
                minMatchCharLength: 1
            };
            
            fuseInstance = new Fuse(searchData, fuseOptions);
            
            // Setup search input event
            const searchInput = document.getElementById('fuzzySearch');
            const searchStatus = document.getElementById('searchStatus');
            const clearBtn = document.getElementById('clearSearch');
            
            if (searchInput && searchStatus) {
                searchInput.addEventListener('input', function(e) {
                    const query = e.target.value.trim();
                    
                    if (query.length < 1) {
                        // Clear filter when search is empty
                        clearSearchFilter();
                        return;
                    }
                    
                    // Perform fuzzy search
                    const results = fuseInstance.search(query);
                    const matchingElements = new Set(results.map(r => r.item.element));
                    
                    // Filter rows - hide non-matching, show matching
                    let visibleCount = 0;
                    searchData.forEach(item => {
                        if (matchingElements.has(item.element)) {
                            item.element.classList.remove('search-hidden');
                            visibleCount++;
                        } else {
                            item.element.classList.add('search-hidden');
                        }
                    });
                    
                    // Update department header visibility
                    updateDepartmentHeadersVisibility();
                    
                    // Show clear button
                    clearBtn.style.display = 'flex';
                    
                    // Update status
                    if (visibleCount === 0) {
                        searchStatus.innerHTML = '<span class="count">No matches found</span> for "' + query + '"';
                    } else {
                        searchStatus.innerHTML = 'Showing <span class="count">' + visibleCount + '</span> matching item(s) for "' + query + '"';
                    }
                    searchStatus.classList.add('active');
                });
            }
        }
        
        // Update department header visibility based on visible rows
        function updateDepartmentHeadersVisibility() {
            const allDeptHeaders = document.querySelectorAll('.department-header');
            
            allDeptHeaders.forEach(header => {
                const deptId = header.getAttribute('data-dept-id');
                const deptRows = document.querySelectorAll('.dept-row[data-dept="' + deptId + '"]');
                
                // Check if any rows in this department are visible (not search-hidden)
                let hasVisibleRows = false;
                deptRows.forEach(row => {
                    if (!row.classList.contains('search-hidden')) {
                        hasVisibleRows = true;
                    }
                });
                
                // Show/hide department header based on visible rows
                if (hasVisibleRows) {
                    header.classList.remove('search-hidden');
                    // Auto-expand department to show filtered results
                    if (header.classList.contains('collapsed')) {
                        deptRows.forEach(row => row.classList.remove('collapsed'));
                        header.classList.remove('collapsed');
                    }
                } else {
                    header.classList.add('search-hidden');
                }
            });
        }
        
        // Clear search filter
        function clearSearchFilter() {
            // Remove search-hidden class from all rows
            const allRows = document.querySelectorAll('.dept-row');
            allRows.forEach(row => row.classList.remove('search-hidden'));
            
            // Remove search-hidden class from all headers
            const allHeaders = document.querySelectorAll('.department-header');
            allHeaders.forEach(header => header.classList.remove('search-hidden'));
            
            // Clear search input
            const searchInput = document.getElementById('fuzzySearch');
            if (searchInput) {
                searchInput.value = '';
            }
            
            // Hide clear button
            const clearBtn = document.getElementById('clearSearch');
            if (clearBtn) {
                clearBtn.style.display = 'none';
            }
            
            // Hide status
            const searchStatus = document.getElementById('searchStatus');
            if (searchStatus) {
                searchStatus.classList.remove('active');
            }
        }
        
        // Context Menu Functions
        function initializeContextMenu() {
            const contextMenu = document.getElementById('contextMenu');
            
            // Show context menu on right-click
            document.addEventListener('contextmenu', function(e) {
                e.preventDefault();
                
                // Position the context menu at mouse location
                contextMenu.style.left = e.pageX + 'px';
                contextMenu.style.top = e.pageY + 'px';
                contextMenu.classList.add('active');
            });
            
            // Hide context menu on regular click
            document.addEventListener('click', function(e) {
                if (!e.target.closest('.context-menu')) {
                    contextMenu.classList.remove('active');
                }
            });
            
            // Hide context menu on scroll
            document.addEventListener('scroll', function() {
                contextMenu.classList.remove('active');
            });
        }
        
        // Collapse all departments
        function collapseAllDepartments() {
            const allDeptHeaders = document.querySelectorAll('.department-header');
            allDeptHeaders.forEach(header => {
                const deptId = header.getAttribute('data-dept-id');
                const deptRows = document.querySelectorAll('.dept-row[data-dept="' + deptId + '"]');
                
                // Collapse if not already collapsed
                if (!header.classList.contains('collapsed')) {
                    deptRows.forEach(row => row.classList.add('collapsed'));
                    header.classList.add('collapsed');
                }
            });
            
            // Hide context menu
            document.getElementById('contextMenu').classList.remove('active');
        }
        
        // Expand all departments
        function expandAllDepartments() {
            const allDeptHeaders = document.querySelectorAll('.department-header');
            allDeptHeaders.forEach(header => {
                const deptId = header.getAttribute('data-dept-id');
                const deptRows = document.querySelectorAll('.dept-row[data-dept="' + deptId + '"]');
                
                // Expand if collapsed
                if (header.classList.contains('collapsed')) {
                    deptRows.forEach(row => row.classList.remove('collapsed'));
                    header.classList.remove('collapsed');
                }
            });
            
            // Hide context menu
            document.getElementById('contextMenu').classList.remove('active');
        }
        
        // Return to top of page
        function returnToTop() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
            
            // Hide context menu
            document.getElementById('contextMenu').classList.remove('active');
        }
        
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
        
        // ========== Minimap Navigation Functions ==========
        
        // Toggle minimap visibility
        function toggleMinimap() {
            const minimap = document.getElementById('minimapNav');
            if (minimap) {
                minimap.classList.toggle('hidden');
            }
        }
        
        // Scroll to a specific section
        function scrollToSection(sectionClass) {
            // Try to find element by class first
            let section = document.querySelector('.' + sectionClass);
            
            // If not found by class, try by ID
            if (!section) {
                section = document.getElementById(sectionClass);
            }
            
            // If still not found, try finding header or section containing the class
            if (!section) {
                section = document.querySelector('[class*="' + sectionClass + '"]');
            }
            
            if (section) {
                const headerOffset = 80; // Offset for fixed elements
                const elementPosition = section.getBoundingClientRect().top;
                const offsetPosition = elementPosition + window.pageYOffset - headerOffset;
                
                window.scrollTo({
                    top: offsetPosition,
                    behavior: 'smooth'
                });
            }
        }
        
        // Update active state of minimap items based on scroll position
        function updateMinimapActiveState() {
            const sections = [
                'report-header',
                'department-summary-section',
                'comparison-section',
                'unmatched-section',
                'summary-section',
                'status-summary'
            ];
            
            const scrollPosition = window.scrollY + 200; // Offset for detection
            
            let activeSection = null;
            
            // Find which section is currently in view
            for (const sectionClass of sections) {
                let section = document.querySelector('.' + sectionClass);
                
                if (!section) {
                    section = document.getElementById(sectionClass);
                }
                
                if (!section) {
                    section = document.querySelector('[class*="' + sectionClass + '"]');
                }
                
                if (section) {
                    const sectionTop = section.offsetTop;
                    const sectionBottom = sectionTop + section.offsetHeight;
                    
                    if (scrollPosition >= sectionTop && scrollPosition < sectionBottom) {
                        activeSection = sectionClass;
                        break;
                    }
                }
            }
            
            // Update active class on minimap items
            const minimapItems = document.querySelectorAll('.minimap-item');
            minimapItems.forEach(item => {
                const itemSection = item.getAttribute('data-section');
                if (itemSection === activeSection) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
        }
        
        // Initialize minimap functionality
        function initializeMinimap() {
            console.log('Initializing minimap navigation...');
            
            // Update active state on scroll
            window.addEventListener('scroll', function() {
                updateMinimapActiveState();
            });
            
            // Set initial active state
            updateMinimapActiveState();
            
            console.log('Minimap navigation initialized');
        }
        
        // Call minimap initialization after DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initializeMinimap);
        } else {
            initializeMinimap();
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
