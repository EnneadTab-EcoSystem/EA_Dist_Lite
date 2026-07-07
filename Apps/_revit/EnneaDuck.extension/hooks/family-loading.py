
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
from EnneadTab.REVIT import REVIT_EVENT, REVIT_CATEGORY
envvars.set_pyrevit_env_var("FAMILY_LOAD_BEGIN", time.time())
datafile = script.get_instance_data_file("sub_c_list")

# print datafile


@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    if not REVIT_EVENT.is_family_load_hook_enabled():
        return
    doc = EXEC_PARAMS.event_args.Document

    # Shared snapshot helper (unicode-coerced signatures) -- kept in one place so
    # the pre (writer) and post (reader) hooks can never drift on the format.
    data = REVIT_CATEGORY.get_subcategory_signatures(doc)

    # json, not pickle: IronPython's protocol-0 pickle emits raw high bytes
    # for non-ASCII category names (0xC3...), corrupting text-mode files and
    # crashing the reader hook (family-loaded.py) with UnicodeDecodeError.
    # ensure_ascii keeps the payload pure ASCII so utf-8 text mode is safe.
    #
    # Serialize BEFORE opening the file: io.open('w') truncates the target the
    # instant it opens, so if json.dumps raised AFTER the open (the old non-ASCII
    # crash) the file was left at 0 bytes -- wiping a previously-good baseline and
    # making the reader dump the whole OST. Building the payload first keeps the
    # write-in-place safe: if dumps ever raises again, the old baseline survives.
    payload = unicode(json.dumps(data, ensure_ascii=True))
    with io.open(datafile, 'w', encoding="utf-8") as f:
        f.write(payload)
############### main ###################
if __name__ == "__main__":
    main()


