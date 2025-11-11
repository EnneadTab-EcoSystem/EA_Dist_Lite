from Autodesk.Revit import DB  # pyright: ignore

TARGET_PANEL_FAMILIES = [
    ("EA_CW-1 (Tower)", "Flat"),
]
TARGET_LINK_TITLE = "SPARC_A_EA_Exterior"
CHILD_FAMILY_NAME = "RefMarker"
EXPECTED_CHILD_COUNT = 4
PIER_MARKER_ORDER = [
    "pier_furring_pt1",
    "pier_furring_pt2",
    "pier_furring_pt3",
    "pier_furring_pt4",
]
ROOM_SEPARATOR_MARKER_ORDER = [
    "rm_line_pt1",
    "rm_line_pt2",
    "rm_line_pt3",
    "rm_line_pt4",
    "rm_line_pt5",
    "rm_line_pt6",
]
ROOM_SEPARATOR_SELECTION_NAME = "ShellRoomSeperationLine(DO_NOT_MANUAL_EDIT)"
FURRING_WALL_TYPE_NAME = "FacadeFurringSpecial(DO_NOT_MANUAL_EDIT)"
PANEL_HEIGHT_PARAMETER = "CWPL_$Height"
MARKER_INDEX_PARAMETER = "index"
PANEL_LOG_PREVIEW_LIMIT = 10
HEIGHT_OFFSET = 3.0  # how much to reduce from the panel height
BASE_OFFSET = 0.0
FAMILY_INSTANCE_FILTER = DB.ElementClassFilter(DB.FamilyInstance)
