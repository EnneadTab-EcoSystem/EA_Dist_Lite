__doc__ = """Force every User Keynote tag in the model to re-pull its displayed text
from the current keynote table.

Some keynote tags go blank even though their key still resolves fine in the keynote
table -- a known Revit caching issue. Reassigning a tag's Key Value parameter is the
only thing that makes Revit redraw the tag; reloading the keynote table alone does not
touch tags that are already placed. A temp-then-restore round trip inside a single
transaction ends on the same value it started with, so Revit's tag-text cache can
treat it as a net no-op and skip the redraw -- exactly like a manual Properties-palette
edit, each tag is toggled through two separately COMMITTED transactions (grouped into
one Undo step) so the temporary value is a real, distinct edit before the key is
restored.

Only User Keynote tags are touched. Element Keynote and Material Keynote tags derive
their Key Value from the tagged element/material, so Revit reports that parameter as
read-only on them (confirmed live) -- they are skipped rather than left to throw.

Features:
- Choose current view only (for testing) or the entire project
- Sweeps the chosen scope's keynote tags in a single undo step
- Count of refreshed and skipped tags shown when it finishes"""
__title__ = "UserKeynote Refresher"
__tip__ = True


import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_SELECTION
from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION
from pyrevit import DB, revit, script, forms

uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()

TEMP_KEY_VALUE = "__ENNEADTAB_KEYNOTE_REFRESH_TEMP__"

OPTION_CURRENT_VIEW = "Current view only (test run)"
OPTION_ENTIRE_PROJECT = "Entire project"


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    scope = forms.SelectFromList.show([OPTION_CURRENT_VIEW, OPTION_ENTIRE_PROJECT],
                                       button_name="Run",
                                       multiselect=False,
                                       title="Refresh keynote tags in...")
    if not scope:
        return

    key_note_tags = DB.FilteredElementCollector(revit.doc).OfCategory(DB.BuiltInCategory.OST_KeynoteTags).WhereElementIsNotElementType().ToElements()

    if scope == OPTION_CURRENT_VIEW:
        active_view = REVIT_APPLICATION.get_active_view()
        key_note_tags = [tag for tag in key_note_tags if tag.OwnerViewId == active_view.Id]

    refreshable = []  # (tag, key_param, original_key)
    skipped_owned_count = 0
    skipped_no_key_count = 0
    skipped_element_or_material_count = 0

    for tag in key_note_tags:
        if not REVIT_SELECTION.is_changable(tag):
            print ("---tag being owned, skip refresh")
            skipped_owned_count += 1
            continue
        view = revit.doc.GetElement(tag.OwnerViewId)
        if not REVIT_SELECTION.is_changable(view):
            print ("---view [{}] being owned, skip refresh".format(view.Name))
            skipped_owned_count += 1
            continue

        key_param = tag.Parameter[DB.BuiltInParameter.KEY_VALUE]
        original_key = key_param.AsString() if key_param else None
        if not key_param or not original_key:
            skipped_no_key_count += 1
            continue

        # Element Keynote and Material Keynote tags derive their Key Value from the
        # tagged element/material, so Revit reports it as read-only on those (confirmed
        # live -- Set() throws "The parameter is read-only"). Only User Keynote tags
        # allow a direct Key Value edit, so this is what keeps this tool User-Keynote-only.
        if key_param.IsReadOnly:
            source_param = tag.Parameter[DB.BuiltInParameter.KEY_SOURCE_PARAM]
            source_text = source_param.AsString() if source_param else "unknown source"
            print ("---tag key value read-only ({}), skip -- not a User Keynote".format(source_text))
            skipped_element_or_material_count += 1
            continue

        refreshable.append((tag, key_param, original_key))

    # A manual edit in the Properties palette works because each edit commits as its
    # own transaction. A temp-then-restore round trip inside a SINGLE transaction ends
    # on the same value it started with, so Revit's tag-text cache can treat it as a
    # net no-op at commit time and skip the redraw. Two separate committed transactions
    # (grouped into one Undo step) force each Set() to be a real, distinct edit.
    with revit.TransactionGroup("refresh keynote tags"):
        with revit.Transaction("keynote refresh - temp key"):
            for tag, key_param, original_key in refreshable:
                key_param.Set(TEMP_KEY_VALUE)

        with revit.Transaction("keynote refresh - restore key"):
            for tag, key_param, original_key in refreshable:
                key_param.Set(original_key)

    # Confirmed live: the Key Value parameter is correctly restored by the transactions
    # above, but the tag's on-screen glyph can still stay stale -- Regenerate() only
    # updates the document model, not view graphics. UpdateAllOpenViews() (2018+) forces
    # a full graphics redraw regardless of what changed, unlike RefreshActiveView(),
    # which several Revit API reports say can still miss tags. Must run outside any
    # open transaction.
    if refreshable:
        uidoc.UpdateAllOpenViews()

    NOTIFICATION.messenger(main_text="{} User Keynote tags refreshed.\n{} skipped due to ownership.\n{} skipped (no key value).\n{} skipped (Element/Material Keynote, not User Keynote).\nSee output for details".format(len(refreshable), skipped_owned_count, skipped_no_key_count, skipped_element_or_material_count))
################## main code below #####################
if __name__ == "__main__":

    output = script.get_output()
    output.close_others()
    main()
