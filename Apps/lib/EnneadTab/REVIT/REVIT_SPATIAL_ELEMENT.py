
"""Utility functions for spatial elements (Rooms and Areas) in Revit.

This module provides functions to determine the status of spatial elements:
- "Not Placed": Element has no Location (Location is None), regardless of Area value
- "Not Enclosed": Element has Location but Area <= 0 (boundaries not properly closed)
- "Good": Element has Location and Area > 0 (properly placed and enclosed)

The detection logic prioritizes Location check first, as a room/area is considered
"Not Placed" if it has no Location, regardless of any Area value it might have.
"""


def get_element_status(element):
    """Determine the status of a spatial element (Room or Area).
    
    Status definitions:
    - "Not Placed": Element has no Location (Location is None), regardless of Area
    - "Not Enclosed": Element has Location but Area <= 0 (boundaries not closed)
    - "Good": Element has Location and Area > 0
    
    Args:
        element: A Revit Room or Area element
        
    Returns:
        str: Status string ("Not Placed", "Not Enclosed", or "Good")
    """
    # Check Location first - if None, element is not placed regardless of Area
    if element.Location is None:
        return "Not Placed"
    
    # If Location exists, check Area
    if element.Area <= 0:
        return "Not Enclosed"
    else:
        return "Good"


def is_element_bad(element):
    return get_element_status(element) != "Good"

def filter_bad_elements(elements):
    """
    return non_closed, non_placed
    """
    non_closed = filter(lambda x: get_element_status(x) == "Not Enclosed", elements)
    non_placed = filter(lambda x: get_element_status(x) == "Not Placed", elements)
    return non_closed, non_placed