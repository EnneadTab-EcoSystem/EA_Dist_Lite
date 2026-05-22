#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Update a Revit color scheme from an Excel file. Pick the workflow that matches your Excel: round-trip (from ColorScheme2Excel) or office template (Department+Program columns)."
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


def _prompt_mode():
    """Ask the user which Excel workflow they're running. Returns _MODE_SINGLE / _MODE_DUAL / None."""
    sub = (
        "Pick the workflow that matches your Excel.\n\n"
        "* Round-trip: you exported from a Revit color scheme via "
        "ColorScheme2Excel, edited colors in Excel, want to push back. "
        "One scheme per Excel.\n\n"
        "* Office Template: you used Ennead's standard color template "
        "with Department + Program columns side-by-side. Two schemes "
        "get updated in one pass."
    )
    res = REVIT_FORMS.dialogue(
        title=__title__,
        main_text="How was this Excel file created?",
        sub_text=sub,
        options=[_MODE_SINGLE, _MODE_DUAL],
    )
    if res not in (_MODE_SINGLE, _MODE_DUAL):
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
    else:
        import dual_channel_form_logic
        dual_channel_form_logic.show(doc)


################## main code below #####################
if __name__ == "__main__":
    excel2_color_scheme()
