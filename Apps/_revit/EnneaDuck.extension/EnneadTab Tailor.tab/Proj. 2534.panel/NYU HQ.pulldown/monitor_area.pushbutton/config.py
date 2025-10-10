#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Configuration file for Monitor Area System
Single source of truth for all configuration settings
"""

# =============================================================================
# PARAMETER MAPPING (Excel ↔ Revit)
# =============================================================================
# Maps logical keys to their Excel column names and Revit parameter names
# This allows Excel to have convenient headers while Revit uses legacy parameter names

APP_EXCEL = "excel"
APP_REVIT = "revit"

DEPARTMENT_KEY = {
    APP_REVIT: "Area_$Department",
    APP_EXCEL: "Department"
}

PROGRAM_TYPE_KEY = {
    APP_REVIT: "Area_$Department_Program Type",
    APP_EXCEL: "Program Type"
}

PROGRAM_TYPE_DETAIL_KEY = {
    APP_REVIT: "Area_$Department_Program Type Detail",
    APP_EXCEL: "Program Type Detail"
}

COUNT_KEY = {
    APP_EXCEL: "COUNT"
}

SCALED_DGSF_KEY = {
    APP_EXCEL: "SCALED DGSF"
}

# =============================================================================
# EXCEL CONFIGURATION
# =============================================================================

# Excel file settings
EXCEL_FILENAME = "Sample.xlsx"
EXCEL_WORKSHEET = "Sheet1"
EXCEL_HEADER_ROW = 2  # Row where headers are located (0-based)

# Primary key for Excel data parsing (use excel version)
EXCEL_PRIMARY_KEY = PROGRAM_TYPE_DETAIL_KEY[APP_EXCEL]

# =============================================================================
# REVIT CONFIGURATION
# =============================================================================



# =============================================================================
# REPORT CONFIGURATION
# =============================================================================

# Report settings
REPORTS_DIR = "reports"
LATEST_REPORT_FILENAME = "latest_report.html"
REPORT_TITLE = "Area Requirements vs Actual - Report"
PROJECT_NAME = "NYU HQ - Monitor Area System"

# HTML table column headers (for display)
TABLE_COLUMN_HEADERS = {
    "area_detail": "Area Detail",
    "department": "Department", 
    "program_type": "Program Type",
    "target_count": "Target Count",
    "target_dgsf": "Target DGSF",
    "actual_count": "Actual Count",
    "actual_dgsf": "Actual DGSF",
    "count_delta": "Count Delta",
    "dgsf_delta": "DGSF Delta",
    "dgsf_percentage": "DGSF %",
    "status": "Status",
    "match_quality": "Match Quality"
}

# =============================================================================
# AREA MATCHING CONFIGURATION
# =============================================================================

# Matching settings
# NOTE: Matching uses EXACT match on all 3 parameters (case-insensitive)
# Department, Program Type, and Program Type Detail must all match exactly
AREA_TOLERANCE_PERCENTAGE = 5.0   # 5% tolerance for area fulfillment status

