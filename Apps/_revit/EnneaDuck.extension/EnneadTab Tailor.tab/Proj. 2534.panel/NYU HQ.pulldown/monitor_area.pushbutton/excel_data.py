#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Excel Data Module - Handles Excel file reading and parsing
"""

import os
import config
from EnneadTab import EXCEL


def get_excel_data():
    """
    Read and parse Excel data using configuration from config.py
    
    Returns:
        dict: Parsed Excel data with requirements
        {
            'key': RowData object with attributes matching column headers
        }
    """
    excel_path = os.path.join(os.path.dirname(__file__), config.EXCEL_FILENAME)
    data = EXCEL.read_data_from_excel(excel_path, worksheet=config.EXCEL_WORKSHEET, return_dict=True)
    data = EXCEL.parse_excel_data(data, key_name=config.EXCEL_PRIMARY_KEY, header_row=config.EXCEL_HEADER_ROW)
    return data
