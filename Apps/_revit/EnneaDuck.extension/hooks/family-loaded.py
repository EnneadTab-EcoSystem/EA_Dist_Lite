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
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, SOUND, NOTIFICATION, TIME, OUTPUT
from EnneadTab.REVIT import REVIT_FORMS, REVIT_EVENT

def _to_unicode(value):
    # IronPython 2.7: .NET Category.Name can arrive as a byte-str holding
    # non-ASCII bytes (e.g. 0xED). Coerce to unicode so the set-diff below
    # compares like-for-like against the unicode names json.load returns from
    # the (ensure_ascii) data file. Without this, non-ASCII names never match
    # and get silently over-reported as "new" subcategories.
    if value is None:
        return u""
    if isinstance(value, unicode):
        return value
    try:
        return value.decode("utf-8")
    except (UnicodeDecodeError, UnicodeError, AttributeError):
        pass
    try:
        return value.decode("mbcs")
    except (UnicodeDecodeError, UnicodeError, LookupError, AttributeError):
        pass
    try:
        return value.decode("latin-1", "replace")
    except (AttributeError, UnicodeError):
        return unicode(value)


def get_subc(category):
    temp = []
    for c in category:
        for sub_c in c.SubCategories:
            temp.append(u"[{0}]--->[{1}]".format(_to_unicode(c.Name), _to_unicode(sub_c.Name)))
    return temp


def difference_list(L1, L2):
    temp = []
    temp.extend( list(set(L1) - set(L2)) )
    temp.extend( list(set(L2) - set(L1)) )
    return temp

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    if not REVIT_EVENT.is_family_load_hook_enabled():
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
    # in the except branch and is treated as an empty baseline once.
    try:
        with io.open(datafile, 'r', encoding="utf-8") as f:
            old_sub_c_list = json.load(f)
    except Exception:
        old_sub_c_list = []
    
    all_Cs = doc.Settings.Categories
    current_sub_c_list = get_subc(all_Cs)
    #print current_sub_c_list

    #print "\n\n\n\n**************************"
    new_sub_c_list =  difference_list(current_sub_c_list, old_sub_c_list)



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
