"""
store session script data to a temp file
https://pyrevit.readthedocs.io/en/latest/pyrevit/coreutils/appdata.html


share parameter between script
https://pyrevit.readthedocs.io/en/latest/pyrevit/coreutils/envvars.html
"""
from pyrevit import script
from pyrevit import EXEC_PARAMS
import io

#from pyrevit.coreutils import appdata
import json
from pyrevit.coreutils import envvars
import time
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, SOUND, NOTIFICATION, TIME, OUTPUT, DATA_CONVERSION, DATA_FILE, USER
from EnneadTab.REVIT import REVIT_FORMS, REVIT_EVENT, REVIT_CATEGORY


def has_required_lib(module, attr_name):
    """Guard against a TORN INSTALL: this hook file is newer than the lib it calls.

    An EnneadTab update copies file-by-file straight into the live EA_Dist folder.
    If it dies partway (Revit holding a file open, network blip), the machine is
    left with the NEW hooks and the OLD lib. The hook then calls a helper that does
    not exist yet and every single family load explodes with a raw

        AttributeError: 'module' object has no attribute 'get_subcategory_signatures'

    which is 94 of the last 100 EnneadTab-OS production ErrorDump events.

    This check is deliberately SELF-CONTAINED -- no new lib helper, no new lib
    import. On a torn install the LIB is the stale half, so anything we factored
    out into a fresh lib module would itself be the thing that is missing, and the
    guard would fail with ImportError instead of AttributeError: same crash, new
    spelling. Only long-standing, always-present APIs are safe to lean on here.

    Duplicated verbatim in the sibling hook family-loading.py. That duplication is
    the feature, not an oversight: these two are the only callers, and the whole
    point is that neither may depend on a shared home a torn update can delete out
    from under it. Edit both or neither.

    Args:
        module: The lib module the hook depends on.
        attr_name (str): The helper the hook is about to call.

    Returns:
        bool: True when the lib is complete and the hook may proceed.
    """
    if hasattr(module, attr_name):
        return True

    message = "EnneadTab install is INCOMPLETE: {}.{} is missing (hook is newer than lib).".format(
        getattr(module, "__name__", "?"), attr_name)
    try:
        ERROR_HANDLE.print_note(message)
        NOTIFICATION.messenger(
            "Your EnneadTab install is incomplete or out of date.\n"
            "Please re-run the EnneadTab installer.")

        # Once per day per missing symbol. Without this gate a torn machine would
        # fire one ErrorDump event per family load -- the exact flood we are here
        # to stop -- just with a friendlier message.
        gate = DATA_FILE.get_data("integrity_report_gate") or {}
        gate_key = "stale_lib_{}".format(attr_name)
        if (time.time() - gate.get(gate_key, 0)) >= 86400.0:
            gate[gate_key] = time.time()
            DATA_FILE.set_data(gate, "integrity_report_gate")
            ERROR_HANDLE.send_error_to_error_dump(
                error_message=message,
                func_name="integrity_torn_install:hook_guard",
                user_name=USER.USER_NAME,
                is_silent=False)
    except Exception:
        # The guard must never become a second source of crashes on a broken install.
        pass
    return False


@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    if not REVIT_EVENT.is_family_load_hook_enabled():
        return

    if not has_required_lib(REVIT_CATEGORY, "get_subcategory_signatures"):
        return

    SOUND.play_sound("sound_effect_mario_coin.wav")


    doc = EXEC_PARAMS.event_args.Document
    if doc.IsFamilyDocument:

        return

    start_time = envvars.get_pyrevit_env_var("FAMILY_LOAD_BEGIN")
    time_pass = time.time() - start_time
    NOTIFICATION.messenger("Family load finished!!\n<{}> Uses {}".format(EXEC_PARAMS.event_args.FamilyName, TIME.get_readable_time(time_pass)))



    #output.print_md("this loaded script")

    datafile = script.get_instance_data_file("sub_c_list")

    # json, not pickle: IronPython's protocol-0 pickle emits raw high bytes for
    # non-ASCII category names (0xC3...), which broke text-mode round-trips
    # fleet-wide (UnicodeDecodeError). json with ensure_ascii stays pure ASCII.
    # A file written by the old pickle code (or a missing/partial file) lands
    # in the except branch -> None baseline -> the guard below skips the diff
    # (with a visible note) instead of dumping the whole object-style list.
    try:
        with io.open(datafile, 'r', encoding="utf-8") as f:
            old_sub_c_list = json.load(f)
    except Exception:
        # None (not []) so the guard below can distinguish "no baseline at all"
        # from a genuine "baseline present, nothing new" case.
        old_sub_c_list = None

    current_sub_c_list = REVIT_CATEGORY.get_subcategory_signatures(doc)

    if not old_sub_c_list:
        # No usable before-snapshot from the pre-load hook (missing / empty /
        # corrupt file, or the pre-hook failed to write one). Without a baseline
        # we CANNOT compute which subcategories are new -- the old code dumped
        # the ENTIRE object-style list here, wrongly labelled as "brought to the
        # project". Surface a concise, visible note instead of a silent skip
        # (never-silent-to-operator) and return without the whole-OST dump.
        NOTIFICATION.messenger("Subcategory diff unavailable for <{}>: no baseline snapshot from the pre-load hook. Reload pyRevit if this repeats.".format(EXEC_PARAMS.event_args.FamilyName))
        ERROR_HANDLE.print_note("family-loaded hook: empty/missing baseline for {}; skipped whole-OST dump.".format(EXEC_PARAMS.event_args.FamilyName))
        return

    # Directional diff: only subcategories present NOW but not before are "new".
    # (The old symmetric difference also reported REMOVED subcategories as
    # "brought to the project", which is wrong.) compare_list returns
    # (only_in_A, only_in_B, shared); only_in_A == current - old == the new ones.
    new_sub_c_list, _removed, _shared = DATA_CONVERSION.compare_list(current_sub_c_list, old_sub_c_list)

    if len(new_sub_c_list) == 0:
        return
    output = OUTPUT.get_output()
 
    output.insert_divider()
    output.write("The following new subCategory(s) are brought to the project [{}] while loading the family [{}]".format(doc.Title, EXEC_PARAMS.event_args.FamilyName), OUTPUT.Style.Subtitle)
    output.write("<{}>".format(EXEC_PARAMS.event_args.FamilyName), OUTPUT.Style.Title)
    output.write(new_sub_c_list)
    
    
    sub_display_text = "\n".join([
        "It happens when new sub-category is created intentionally, but also when you load a family:",
        "",
        "--from other project;",
        "--from manufacture website;",
        "--with a typo to an existing sub-category name.",
        "",
        "If this is unintensional, please take notes and use Ideate 'StyleManager' tool to manage object style later."
        ])
    output.write(sub_display_text, OUTPUT.Style.Footnote)

    output.plot()
    return
    REVIT_FORMS.notification(main_text = display_text,
                            sub_text = sub_display_text,
                            self_destruct = 5,
                            window_width = 650)

#############  main    ###########
if __name__ == "__main__":

    main()
