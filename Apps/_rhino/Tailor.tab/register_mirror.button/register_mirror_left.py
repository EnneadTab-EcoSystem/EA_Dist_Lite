
__title__ = "RegisterMirror"
__doc__ = """Mirror Command Shortcut Registration Tool

Registers keyboard shortcuts for mirror commands with and without copy options.
Features:
- Registers F1 key for mirror with copy (_mirror _copy=Yes)
- Registers F2 key for mirror without copy (_mirror _copy=No)
- Uses Rhino alias system for persistent shortcuts
- Provides user notification of successful registration
- Designed for efficient mirror operations in modeling workflow

Shortcuts:
- F1: Mirror with copy (creates duplicate objects)
- F2: Mirror without copy (moves existing objects)

Usage:
- Run tool to register shortcuts
- Use F1/F2 keys for quick mirror operations
- Shortcuts persist across Rhino sessions
- Provides feedback on successful registration"""


from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from EnneadTab.RHINO import RHINO_ALIAS

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def register_mirror():

    RHINO_ALIAS.register_shortcut("F1", "_mirror _copy=Yes ")
    RHINO_ALIAS.register_shortcut("F2", "_mirror _copy=No ")
    NOTIFICATION.messenger("You have registered the shortcut \"F1\" to mirror with copy and \"F2\" for mirror without copy")

    
if __name__ == "__main__":
    register_mirror()
