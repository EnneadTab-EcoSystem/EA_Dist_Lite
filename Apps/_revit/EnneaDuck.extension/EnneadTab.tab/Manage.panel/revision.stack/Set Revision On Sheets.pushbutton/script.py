__title__ = "Set Revision On Sheets"
__doc__ = """Add one or more revisions to many sheets at once.

Pick the revisions, then pick the sheets to stamp them on. Every sheet is updated
in a single undo step, and each one is listed in the output window so you can
confirm the issue went where you meant it to.

Usage:
1. Pick the revisions to add
2. Pick the target sheets
3. Review the updated sheets in the output window"""

from pyrevit import revit, DB
from pyrevit import forms
from EnneadTab.REVIT import REVIT_APPLICATION
from pyrevit import script
from pyrevit.framework import List
from pyrevit.revit.db import query


def update_sheet_revisions(revisions, sheets=None, state=True):
    doc = revit.doc
    # make sure revisions is a list
    if not isinstance(revisions, list):
        revisions = [revisions]

    updated_sheets = []
    if revisions:
        # get sheets if not available
        for sheet in sheets or query.get_sheets(doc=doc):
            addrevs = set([REVIT_APPLICATION.get_element_id_value(x)
                           for x in sheet.GetAdditionalRevisionIds()])
            for rev in revisions:
                # skip issued revisions
                rev_id = REVIT_APPLICATION.get_element_id_value(rev.Id)
                if state:
                    addrevs.add(rev_id)
                elif rev_id in addrevs:
                    addrevs.remove(rev_id)

            rev_elids = [DB.ElementId(x) for x in addrevs]
            sheet.SetAdditionalRevisionIds(List[DB.ElementId](rev_elids))
            updated_sheets.append(sheet)

    return updated_sheets


if __name__== "__main__":
    revisions = forms.select_revisions(button_name='Select Revision',
                                       multiple=True)
    if revisions:
        sheets = forms.select_sheets(button_name='Set Revision',
                                     include_placeholder=True)
        if sheets:
            with revit.Transaction('Set Revision on Sheets'):
                updated_sheets = update_sheet_revisions(revisions,
                                                        sheets)
            if updated_sheets:
                print('SELECTED REVISION ADDED TO THESE SHEETS:')
                print('-' * 100)
                for s in updated_sheets:
                    snum = s.Parameter[DB.BuiltInParameter.SHEET_NUMBER]\
                            .AsString().rjust(10)
                    sname = s.Parameter[DB.BuiltInParameter.SHEET_NAME]\
                             .AsString().ljust(50)
                    print('NUMBER: {0}   NAME:{1}'.format(snum, sname))