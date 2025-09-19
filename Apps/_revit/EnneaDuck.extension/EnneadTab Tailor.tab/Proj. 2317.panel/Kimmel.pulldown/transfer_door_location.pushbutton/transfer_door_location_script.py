#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Transfer door location based on room analysis across phases. 
Automatically sets door location parameter based on connected rooms, 
prioritizing non-corridor rooms and smaller rooms when both sides are valid."""
__title__ = "Transfer Door Location"

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
EXISTING_PHASE_NAME = "Existing"
CORRIDOR_DEFAULT = "CORRIDOR"


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


def is_ignored_room(room_name):
    """Check if room name should be ignored (corridor/hallway)."""
    return room_name.lower() in IGNORE_ROOM_NAMES


def select_best_room(to_room, from_room, to_room_name, from_room_name):
    """
    Select the best room based on priority rules:
    1. Prefer non-corridor rooms
    2. If both are corridors, return CORRIDOR
    3. If both are valid rooms, prefer smaller room
    """
    # If one room is empty, return the other
    if not to_room_name and not from_room_name:
        return ""
    elif not to_room_name:
        return from_room_name
    elif not from_room_name:
        return to_room_name
    
    # If both are corridors, return CORRIDOR
    if is_ignored_room(to_room_name) and is_ignored_room(from_room_name):
        return CORRIDOR_DEFAULT
    
    # If one is corridor, prefer the other
    if is_ignored_room(to_room_name):
        return from_room_name
    elif is_ignored_room(from_room_name):
        return to_room_name
    
    # Both are valid rooms - prefer smaller room
    if to_room and from_room:
        smaller_room = to_room if to_room.Area <= from_room.Area else from_room
        return get_room_name(smaller_room)
    
    # This should never be reached - raise exception for unexpected condition
    raise Exception("Unexpected condition. To room: {}, From room: {}".format(to_room_name, from_room_name))


def process_door_location(door, phases, output):
    """Process a single door's location across all phases."""
    mark_param = door.LookupParameter(MARK_PARAM_NAME)
    door_number = mark_param.AsString() if mark_param else "Unknown"
    
    print("\n\nDoor: {}".format(output.linkify(door.Id, title=door_number)))
    
    location_param = door.LookupParameter(LOCATION_PARAM_NAME)
    if not location_param:
        ERROR_HANDLE.print_note("Door {} has no Location parameter".format(door_number))
        return
    
    best_location = ""
    
    for phase in phases:
        to_room = door.ToRoom[phase] if door.ToRoom else None
        from_room = door.FromRoom[phase] if door.FromRoom else None
        
        to_room_name = get_room_name(to_room)
        from_room_name = get_room_name(from_room)
        
        print("  {}: to_room=[{}], from_room=[{}]".format(phase.Name, to_room_name, from_room_name))
        
        selected_room = select_best_room(to_room, from_room, to_room_name, from_room_name)
        
        if selected_room and selected_room != CORRIDOR_DEFAULT:
            best_location = selected_room
            print("    Selected: {}".format(selected_room))
            break
        elif selected_room == CORRIDOR_DEFAULT:
            best_location = CORRIDOR_DEFAULT
    
    # Set the final location
    if best_location:
        location_param.Set(best_location)
        print("!!!!!!!!!!! Setting location as: {}".format(best_location))


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def transfer_door_locations(doc):
    """Main function to transfer door locations based on room analysis."""
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
    t = DB.Transaction(doc, "Transfer Door Locations")
    t.Start()
    
    processed_count = 0
    for door in all_doors:
        # Skip doors in existing phase
        created_phase = doc.GetElement(door.CreatedPhaseId)
        if created_phase and created_phase.Name == EXISTING_PHASE_NAME:
            continue
        
        process_door_location(door, phases, output)
        processed_count += 1
    
    t.Commit()
    print("\nProcessed {} doors successfully".format(processed_count))


################## main code below #####################

if __name__ == "__main__":
    transfer_door_locations(DOC)