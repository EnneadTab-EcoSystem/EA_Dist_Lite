#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Push colors edited in Excel back into a Revit color scheme.

Edit your colors where it is comfortable, then bring them back in one step. Two
workflows are supported and the button asks which one your spreadsheet came from.

Features:
- Round-trip: for a spreadsheet you exported with ColorScheme2Excel, one scheme per file
- Office template: for the standard Ennead sheet with Department and Program columns
  side by side, which updates both schemes in one pass
- Online: no Excel needed - pull the project's color book straight from enneadtab.com
  (Department + Program), applied in one pass. Sign in once when prompted.

Usage:
1. Run the button and pick the source (Excel round-trip, Excel office template, or Online)
2. For Excel: pick the file and scheme. For Online: enter the project number and sector."""
__title__ = "Excel2ColorScheme"

import os
import sys

import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS

# Make the forms/ subdirectory importable.
_FORMS_DIR = os.path.join(os.path.dirname(__file__), "forms")
if _FORMS_DIR not in sys.path:
    sys.path.append(_FORMS_DIR)


_MODE_SINGLE = "Round-trip (Single Scheme)"
_MODE_DUAL = "Office Template (Dual Scheme)"
_MODE_ONLINE = "Online (Project Book)"


def _prompt_mode():
    """Ask which workflow to run. Returns _MODE_SINGLE / _MODE_DUAL / _MODE_ONLINE / None."""
    sub = (
        "Pick your source.\n\n"
        "* Round-trip: you exported from a Revit color scheme via "
        "ColorScheme2Excel, edited colors in Excel, want to push back. "
        "One scheme per Excel.\n\n"
        "* Office Template: you used Ennead's standard color template "
        "with Department + Program columns side-by-side. Two schemes "
        "get updated in one pass.\n\n"
        "* Online: no Excel needed. Pull the project's color book straight "
        "from enneadtab.com (Department + Program), applied in one pass. "
        "Sign in once when prompted."
    )
    res = REVIT_FORMS.dialogue(
        title=__title__,
        main_text="Where do the colors come from?",
        sub_text=sub,
        options=[_MODE_SINGLE, _MODE_DUAL, _MODE_ONLINE],
    )
    if res not in (_MODE_SINGLE, _MODE_DUAL, _MODE_ONLINE):
        return None
    return res


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def excel2_color_scheme():
    doc = REVIT_APPLICATION.get_doc()
    mode = _prompt_mode()
    if mode is None:
        print("Excel2ColorScheme: cancelled at mode picker.")
        return

    if mode == _MODE_SINGLE:
        import single_channel_form_logic
        single_channel_form_logic.show(doc)
    elif mode == _MODE_ONLINE:
        import online_channel_form_logic
        online_channel_form_logic.show(doc)
    else:
        import dual_channel_form_logic
        dual_channel_form_logic.show(doc)


################## main code below #####################
if __name__ == "__main__":
    excel2_color_scheme()
