#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Parameter Updater Module - Updates Revit area parameters with suggestions
Handles both matched areas (clear suggestion) and unmatched areas (set suggestion)
"""

from Autodesk.Revit import DB # pyright: ignore
from EnneadTab.REVIT import REVIT_SELECTION
import config


def update_area_parameters(doc, matches_by_scheme, unmatched_by_scheme):
    """
    Update UnMatchedSuggestion parameter for all areas
    - Matched areas: Clear the parameter
    - Unmatched areas: Set suggestion text
    
    Args:
        doc: Revit document
        matches_by_scheme: Dictionary of matches by scheme from AreaMatcher
        unmatched_by_scheme: Dictionary of unmatched areas by scheme
        
    Returns:
        dict: Statistics about the update operation
    """
    print("\n=== PARAMETER UPDATE DEBUG ===")
    print("Matches by scheme keys: {}".format(matches_by_scheme.keys()))
    print("Unmatched by scheme keys: {}".format(unmatched_by_scheme.keys()))
    
    stats = {
        'matched_cleared': 0,
        'matched_skipped': 0,
        'unmatched_updated': 0,
        'unmatched_skipped': 0,
        'errors': []
    }
    
    # Start a transaction to modify parameters
    transaction = DB.Transaction(doc, "Update Area Suggestions")
    transaction.Start()
    
    try:
        # Process matched areas - clear the suggestion parameter
        for scheme_name, scheme_data in matches_by_scheme.items():
            matches = scheme_data.get('matches', [])
            for match in matches:
                matching_areas = match.get('matching_areas', [])
                for area_object in matching_areas:
                    result = _clear_suggestion_parameter(area_object)
                    if result['success']:
                        stats['matched_cleared'] += 1
                    else:
                        stats['matched_skipped'] += 1
                        if result.get('error'):
                            stats['errors'].append(result['error'])
        
        # Process unmatched areas - set suggestion text
        for scheme_name, unmatched_areas in unmatched_by_scheme.items():
            print("Processing {} unmatched areas for scheme: {}".format(len(unmatched_areas), scheme_name))
            for area_object in unmatched_areas:
                result = _set_suggestion_parameter(area_object)
                if result['success']:
                    stats['unmatched_updated'] += 1
                else:
                    stats['unmatched_skipped'] += 1
                    if result.get('error'):
                        stats['errors'].append(result['error'])
                        print("  Skipped area - Error: {}".format(result['error']))
        
        transaction.Commit()
        print("Transaction committed successfully")
        
    except Exception as e:
        transaction.RollBack()
        stats['errors'].append("Transaction failed: {}".format(str(e)))
        print("Transaction rolled back - Error: {}".format(str(e)))
    
    print("\n=== PARAMETER UPDATE STATS ===")
    print("Matched cleared: {}".format(stats['matched_cleared']))
    print("Matched skipped: {}".format(stats['matched_skipped']))
    print("Unmatched updated: {}".format(stats['unmatched_updated']))
    print("Unmatched skipped: {}".format(stats['unmatched_skipped']))
    print("Errors: {}".format(len(stats['errors'])))
    if stats['errors']:
        print("Error details:")
        for error in stats['errors'][:5]:  # Show first 5 errors
            print("  - {}".format(error))
    print("=== END DEBUG ===\n")
    
    return stats


def _clear_suggestion_parameter(area_object):
    """
    Clear the UnMatchedSuggestion parameter for a matched area
    
    Args:
        area_object: Dictionary containing area data including 'revit_element'
        
    Returns:
        dict: Result with 'success' boolean and optional 'error' message
    """
    result = {'success': False}
    
    try:
        area = area_object.get('revit_element')
        if not area:
            result['error'] = "No Revit element reference found"
            return result
        
        # Check if element is editable using EnneadTab utility
        if not REVIT_SELECTION.is_changable(area):
            result['error'] = "Element not editable (checked out by another user)"
            return result
        
        # Get the parameter
        param = area.LookupParameter(config.UNMATCHED_SUGGESTION_PARAM)
        
        if not param:
            # Parameter doesn't exist - that's okay, nothing to clear
            result['success'] = True
            return result
        
        if param.IsReadOnly:
            result['error'] = "Parameter is read-only"
            return result
        
        # Clear the parameter (set to empty string)
        param.Set("")
        result['success'] = True
        
    except Exception as e:
        result['error'] = "Error clearing parameter: {}".format(str(e))
    
    return result


def _set_suggestion_parameter(area_object):
    """
    Set the UnMatchedSuggestion parameter for an unmatched area
    
    Args:
        area_object: Dictionary containing area data including suggestion info
        
    Returns:
        dict: Result with 'success' boolean and optional 'error' message
    """
    result = {'success': False}
    
    try:
        area = area_object.get('revit_element')
        if not area:
            result['error'] = "No Revit element reference found"
            return result
        
        # Check if element is editable using EnneadTab utility
        if not REVIT_SELECTION.is_changable(area):
            result['error'] = "Element not editable (checked out by another user)"
            return result
        
        # Get the parameter
        param = area.LookupParameter(config.UNMATCHED_SUGGESTION_PARAM)
        
        if not param:
            result['error'] = "Parameter '{}' not found in area".format(config.UNMATCHED_SUGGESTION_PARAM)
            return result
        
        if param.IsReadOnly:
            result['error'] = "Parameter is read-only"
            return result
        
        # Get suggestion from area_object or generate it
        suggestion_text = area_object.get('suggestion_text', '')
        
        # If no suggestion text is stored, create it from area data
        if not suggestion_text:
            suggestion_text = _generate_no_suggestion_text()
        
        print("    Setting suggestion: '{}'".format(suggestion_text))
        
        # Set the parameter
        param.Set(suggestion_text)
        result['success'] = True
        
    except Exception as e:
        result['error'] = "Error setting parameter: {}".format(str(e))
    
    return result


def _generate_no_suggestion_text():
    """
    Generate text when no suggestion is available
    
    Returns:
        str: Default text for no suggestion
    """
    return "No matching suggestion found"


def generate_suggestion_text(department, division, room_name):
    """
    Generate formatted suggestion text for display
    
    Args:
        department: Department value
        division: Division/Program Type value
        room_name: Room Name/Program Type Detail value
        
    Returns:
        str: Formatted suggestion text
    """
    return "{} | {} | {}".format(department, division, room_name)

