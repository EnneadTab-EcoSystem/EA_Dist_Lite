#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Transfer door location and mark based on room analysis across phases. 

LOCATION PARAMETER:
- Analyzes all phases to find connected rooms
- Prioritizes non-corridor rooms over corridors
- For two valid rooms, selects the smaller one
- Sets location to room name

MARK PARAMETER:
- Single door to a room: Mark = Room Number (e.g., "101")
- Multiple doors to same room: Mark = Room Number + A/B/C (e.g., "101A", "101B")
- Doors sorted by Element ID for consistent suffix assignment

SPECIAL CASES:
- Normal room: Location=Room Name, Mark=Room Number
- Corridor: Location="CORRIDOR", Mark=Corridor Room Number
- No room around door: Location="no room", Mark="no room"
- Room exists but no name: Location="missing room name", Mark=Room Number
- Room exists but no number: Location=Room Name, Mark="missing room number"

PHASES:
- Skips doors created in "Existing" phase
- Processes all other phases until a valid room is found"""
__title__ = "Door Location and Mark"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION
from Autodesk.Revit import DB # pyright: ignore 

DOC = REVIT_APPLICATION.get_doc()
from pyrevit import script
output = script.get_output()
output.close_others()

# Constants
IGNORE_ROOM_NAMES = {"corridor", "hallway"}
LOCATION_PARAM_NAME = "Location"
MARK_PARAM_NAME = "Mark"
ROOM_NAME_PARAM = "Name"
ROOM_NUMBER_PARAM = "Number"
EXISTING_PHASE_NAME = "Existing"
CORRIDOR_DEFAULT = "CORRIDOR"
MISSING_ROOM_NUMBER = "missing room number"
NO_ROOM_DEFAULT = "no room"
MISSING_ROOM_NAME = "missing room name"


def get_all_phases(doc):
    """Get all phases in the document sorted by name."""
    all_phase_ids = DB.FilteredElementCollector(doc).OfClass(DB.Phase).ToElementIds()
    phases = [doc.GetElement(phase_id) for phase_id in all_phase_ids]
    return sorted(phases, key=lambda x: x.Name)


def get_room_name(room):
    """Safely get room name parameter value."""
    if not room:
        return ""
    param = room.LookupParameter(ROOM_NAME_PARAM)
    return param.AsString() if param else ""


def get_room_number(room):
    """Safely get room number parameter value."""
    if not room:
        return MISSING_ROOM_NUMBER
    param = room.LookupParameter(ROOM_NUMBER_PARAM)
    room_number = param.AsString() if param else ""
    return room_number if room_number else MISSING_ROOM_NUMBER


def is_ignored_room(room_name):
    """Check if room name should be ignored (corridor/hallway)."""
    return room_name.lower() in IGNORE_ROOM_NAMES


def select_best_room(to_room, from_room, to_room_name, from_room_name):
    """
    Select the best room based on priority rules:
    1. Prefer non-corridor rooms
    2. If both are corridors, return (CORRIDOR, None)
    3. If both are valid rooms, prefer smaller room
    
    Returns: tuple (location_string, room_object)
    """
    # If one room is empty, return the other
    if not to_room_name and not from_room_name:
        return ("", None)
    elif not to_room_name:
        return (from_room_name, from_room)
    elif not from_room_name:
        return (to_room_name, to_room)
    
    # If both are corridors, return CORRIDOR
    if is_ignored_room(to_room_name) and is_ignored_room(from_room_name):
        return (CORRIDOR_DEFAULT, None)
    
    # If one is corridor, prefer the other
    if is_ignored_room(to_room_name):
        return (from_room_name, from_room)
    elif is_ignored_room(from_room_name):
        return (to_room_name, to_room)
    
    # Both are valid rooms - prefer smaller room
    if to_room and from_room:
        smaller_room = to_room if to_room.Area <= from_room.Area else from_room
        return (get_room_name(smaller_room), smaller_room)
    
    # This should never be reached - raise exception for unexpected condition
    raise Exception("Unexpected condition. To room: {}, From room: {}".format(to_room_name, from_room_name))


def process_door_location(door, phases, output):
    """
    Process a single door's location across all phases.
    Returns: tuple (location_string, room_object) - always returns a result
    """
    mark_param = door.LookupParameter(MARK_PARAM_NAME)
    door_number = mark_param.AsString() if mark_param else "Unknown"
    
    print("\n\nDoor: {}".format(output.linkify(door.Id, title=door_number)))
    
    location_param = door.LookupParameter(LOCATION_PARAM_NAME)
    if not location_param:
        ERROR_HANDLE.print_note("Door {} has no Location parameter".format(door_number))
        return (NO_ROOM_DEFAULT, None)
    
    best_location = ""
    best_room = None
    found_room = False
    
    for phase in phases:
        to_room = door.ToRoom[phase] if door.ToRoom else None
        from_room = door.FromRoom[phase] if door.FromRoom else None
        
        to_room_name = get_room_name(to_room)
        from_room_name = get_room_name(from_room)
        
        print("  {}: to_room=[{}], from_room=[{}]".format(phase.Name, to_room_name, from_room_name))
        
        location_string, room_object = select_best_room(to_room, from_room, to_room_name, from_room_name)
        
        if location_string and location_string != CORRIDOR_DEFAULT:
            best_location = location_string
            best_room = room_object
            found_room = True
            print("    Selected: {}".format(location_string))
            break
        elif location_string == CORRIDOR_DEFAULT:
            best_location = CORRIDOR_DEFAULT
            best_room = None
            found_room = True
        elif room_object:
            # Room exists but has no name
            best_room = room_object
            found_room = True
    
    # Set the final location
    if best_location:
        location_param.Set(best_location)
        print("!!!!!!!!!!! Setting location as: {}".format(best_location))
    elif found_room and best_room:
        # Room exists but no name - set location as missing room name
        location_param.Set(MISSING_ROOM_NAME)
        print("!!!!!!!!!!! Setting location as: {} (room exists but no name)".format(MISSING_ROOM_NAME))
        return (MISSING_ROOM_NAME, best_room)
    else:
        # No room found at all
        location_param.Set(NO_ROOM_DEFAULT)
        print("!!!!!!!!!!! Setting location as: {} (no room found)".format(NO_ROOM_DEFAULT))
        return (NO_ROOM_DEFAULT, None)
    
    return (best_location, best_room)


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def transfer_door_locations(doc):
    """Main function to transfer door locations and marks based on room analysis."""
    # Get all phases
    phases = get_all_phases(doc)
    if not phases:
        ERROR_HANDLE.print_note("No phases found in document")
        return
    
    print("Found {} phases: {}".format(len(phases), [p.Name for p in phases]))
    
    # Get all doors
    all_doors = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Doors).WhereElementIsNotElementType().ToElements()
    print("Found {} doors".format(len(all_doors)))
    
    # Start transaction
    t = DB.Transaction(doc, "Transfer Door Locations and Marks")
    t.Start()
    
    # PASS 1: Process all doors to determine locations and track room associations
    print("\n=== PASS 1: Determining door locations ===")
    door_location_map = {}  # {door: (location_string, room_object)}
    
    processed_count = 0
    for door in all_doors:
        # Skip doors in existing phase
        created_phase = doc.GetElement(door.CreatedPhaseId)
        if created_phase and created_phase.Name == EXISTING_PHASE_NAME:
            continue
        
        result = process_door_location(door, phases, output)
        door_location_map[door] = result
        processed_count += 1
    
    print("\nPass 1 complete: Processed {} doors".format(processed_count))
    
    # PASS 2: Assign door marks based on room numbers
    print("\n=== PASS 2: Assigning door marks ===")
    
    # Group doors by room ID (not room name!) to handle duplicate room names
    room_groups = {}  # {room_id: [(door, location_string, room_object), ...]}
    for door, (location_string, room_object) in door_location_map.items():
        # Use room ID as key; for special cases (no room, corridor), use location_string
        if room_object:
            group_key = room_object.Id.IntegerValue
        else:
            # For special cases like "no room" or "CORRIDOR", use location_string
            group_key = location_string
        
        if group_key not in room_groups:
            room_groups[group_key] = []
        room_groups[group_key].append((door, location_string, room_object))
    
    # Process each room group
    for group_key, door_info_list in room_groups.items():
        # Get location and room info from first door in group
        _first_door, location_string, room_object = door_info_list[0]
        print("\nLocation: {} (Group Key: {})".format(location_string, group_key))
        
        # Sort doors by element ID
        sorted_pairs = sorted(door_info_list, key=lambda x: x[0].Id.IntegerValue)
        
        # Handle special cases
        if location_string == NO_ROOM_DEFAULT:
            # No room found - set all door marks to "no room"
            print("  Special case: No room found")
            for door, _loc_str, _room_obj in sorted_pairs:
                mark_param = door.LookupParameter(MARK_PARAM_NAME)
                if mark_param:
                    mark_param.Set(NO_ROOM_DEFAULT)
                    print("    Door {} -> Mark: {}".format(output.linkify(door.Id), NO_ROOM_DEFAULT))
            continue
        
        # Get room number from the room object
        room_number = get_room_number(room_object)
        
        print("  Room number: {}".format(room_number))
        print("  Doors to this location: {}".format(len(sorted_pairs)))
        
        # Assign marks
        if len(sorted_pairs) == 1:
            # Single door - use room number as-is
            door = sorted_pairs[0][0]
            mark_param = door.LookupParameter(MARK_PARAM_NAME)
            if mark_param:
                mark_param.Set(room_number)
                print("    Door {} -> Mark: {}".format(output.linkify(door.Id), room_number))
        else:
            # Multiple doors - append A, B, C, etc.
            for i, (door, _loc_str, _room_obj) in enumerate(sorted_pairs):
                suffix = chr(65 + i)  # 65 is ASCII for 'A'
                door_mark = "{}{}".format(room_number, suffix)
                mark_param = door.LookupParameter(MARK_PARAM_NAME)
                if mark_param:
                    mark_param.Set(door_mark)
                    print("    Door {} -> Mark: {}".format(output.linkify(door.Id), door_mark))
    
    t.Commit()
    print("\n=== Complete: Processed {} doors successfully ===".format(processed_count))


################## main code below #####################

if __name__ == "__main__":
    transfer_door_locations(DOC)