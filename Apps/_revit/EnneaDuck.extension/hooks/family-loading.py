
"""
store session script data to a temp file
https://pyrevit.readthedocs.io/en/latest/pyrevit/coreutils/appdata.html


share parameter between script
https://pyrevit.readthedocs.io/en/latest/pyrevit/coreutils/envvars.html
"""

import io
from pyrevit import script
from pyrevit import EXEC_PARAMS
# from pyrevit.coreutils import appdata
from pyrevit.coreutils import envvars
import time
import json
import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE
from EnneadTab.REVIT import REVIT_EVENT
envvars.set_pyrevit_env_var("FAMILY_LOAD_BEGIN", time.time())
datafile = script.get_instance_data_file("sub_c_list")

# print datafile


def _to_unicode(value):
    # IronPython 2.7: .NET Category.Name can arrive as a byte-str holding
    # non-ASCII bytes (e.g. 0xED). json.dumps then triggers an implicit
    # str.decode('ascii') and dies with UnicodeDecodeError. Coerce every name
    # to unicode BEFORE it reaches .format()/json so only unicode is produced.
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
            # unicode template + coerced names => json.dumps never sees a
            # byte-str, so non-ASCII subcategory names can't crash the writer.
            temp.append(u"[{0}]--->[{1}]".format(_to_unicode(c.Name), _to_unicode(sub_c.Name)))
    return temp

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    if not REVIT_EVENT.is_family_load_hook_enabled():
        return
    doc = EXEC_PARAMS.event_args.Document

    all_Cs = doc.Settings.Categories

    data = get_subc(all_Cs)

    # json, not pickle: IronPython's protocol-0 pickle emits raw high bytes
    # for non-ASCII category names (0xC3...), corrupting text-mode files and
    # crashing the reader hook (family-loaded.py) with UnicodeDecodeError.
    # ensure_ascii keeps the payload pure ASCII so utf-8 text mode is safe.
    with io.open(datafile, 'w', encoding="utf-8") as f:
        f.write(unicode(json.dumps(data, ensure_ascii=True)))
############### main ###################
if __name__ == "__main__":
    main()


