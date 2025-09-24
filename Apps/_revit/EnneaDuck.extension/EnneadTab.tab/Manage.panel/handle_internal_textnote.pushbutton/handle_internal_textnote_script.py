#!/usr/bin/python
# -*- coding: utf-8 -*-

INTERNAL_TYPE_NAME_PREFIX = "_internal_note"
__doc__ = """Handle internal textnotes and dimensions in the project.
This tool allows you to show or hide all internal textnotes and dimensions at once.
Filters elements by type names that begin with '_internal_note' prefix.
Works across all views including dependent views while respecting ownership permissions."""

__title__ = "Internal Annotation\nHandler"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG, NOTIFICATION, DATA_CONVERSION
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS, REVIT_SELECTION
from Autodesk.Revit import DB # pyright: ignore 

UIDOC = REVIT_APPLICATION.get_uidoc()
DOC = REVIT_APPLICATION.get_doc()


class InternalAnnotationHandler:
    """Handler class for managing internal textnotes and dimensions visibility."""
    
    def __init__(self, doc):
        """Initialize the handler.
        
        Args:
            doc: Current Revit document
        """
        self.doc = doc
        self.internal_textnotes = []
        self.internal_dimensions = []
        self.editable_annotations = []
        self.unchanged = 0
        self.unchanged_owners = set()
        self.modified = 0
        
    def get_internal_annotations(self):
        """Get all internal textnotes and dimensions in the project."""
        # Get textnotes
        textnote_collector = DB.FilteredElementCollector(self.doc).OfClass(DB.TextNote)
        all_textnotes = list(textnote_collector.ToElements())
        
        self.internal_textnotes = [note for note in all_textnotes 
                                 if note.TextNoteType.LookupParameter("Type Name").AsString().startswith(INTERNAL_TYPE_NAME_PREFIX)]
        
        # Get dimensions
        dimension_collector = DB.FilteredElementCollector(self.doc).OfClass(DB.Dimension)
        all_dimensions = list(dimension_collector.ToElements())
        
        self.internal_dimensions = [dim for dim in all_dimensions 
                                  if dim.DimensionType.LookupParameter("Type Name").AsString().startswith(INTERNAL_TYPE_NAME_PREFIX)]
        
        total_internal = len(self.internal_textnotes) + len(self.internal_dimensions)
        return bool(total_internal)
        
    def get_user_choice(self):
        """Show dialog for user to choose show/hide action.
        
        Returns:
            bool: True for show, False for hide, None if cancelled
        """
        options = ["Show all internal annotations", "Hide all internal annotations"]
        res = REVIT_FORMS.dialogue(main_text="Internal Annotation Visibility",
                                  sub_text="Any annotation(textnote or dimension) with type name starting with '{}' will be considered internal.\nUse internal notes to create non-plot annotations.".format(INTERNAL_TYPE_NAME_PREFIX),
                                  options=options)
        
        if not res:
            return None
        return res == options[0]
        
    def process_annotations(self):
        """Process annotations to separate editable and non-editable ones."""
        self.editable_annotations = []
        self.unchanged = 0
        self.unchanged_owners = set()
        
        # Process textnotes
        for note in self.internal_textnotes:
            if REVIT_SELECTION.is_changable(note):
                self.editable_annotations.append(note)
            else:
                self.unchanged += 1
                owner = REVIT_SELECTION.get_owner(note)
                if owner:
                    self.unchanged_owners.add(owner)
        
        # Process dimensions
        for dim in self.internal_dimensions:
            if REVIT_SELECTION.is_changable(dim):
                self.editable_annotations.append(dim)
            else:
                self.unchanged += 1
                owner = REVIT_SELECTION.get_owner(dim)
                if owner:
                    self.unchanged_owners.add(owner)
                    
        return bool(self.editable_annotations)
        
    def modify_visibility(self, show_annotations):
        """Modify visibility of each annotation in its owner view and dependent views.
        
        Args:
            show_annotations: True to show, False to hide
        """
        self.modified = 0
        self.show_annotations = show_annotations  # Store the state for reporting
        t = DB.Transaction(self.doc, __title__)
        t.Start()
        
        for annotation in self.editable_annotations:
            view_id = annotation.OwnerViewId
            view = self.doc.GetElement(view_id)
            
            # Get all views to process (main view + dependent views)
            views_to_do = [view]
            dependent_view_ids = list(view.GetDependentViewIds())
            if dependent_view_ids:
                views_to_do.extend([self.doc.GetElement(x) for x in dependent_view_ids])
            
            # Process each view (main + dependent)
            for current_view in views_to_do:
                if not current_view:
                    print("Cannot process view: {}".format(view.Name if view else "Unknown"))
                    continue
                
                # Check if view is owned by others
                if not REVIT_SELECTION.is_changable(current_view):
                    owner = REVIT_SELECTION.get_owner(current_view)
                    print("Skipping view '{}' - owned by: {}".format(current_view.Name, owner if owner else "others"))
                    continue
                
                element_ids = DATA_CONVERSION.list_to_system_list([annotation.Id])
                if show_annotations:
                    current_view.UnhideElements(element_ids)
                else:
                    current_view.HideElements(element_ids)
            
            self.modified += 1
            
        t.Commit()
        
    def report_results(self):
        """Generate and show results message."""
        message = "Modified {} internal annotations as {}.".format(self.modified, "visible" if self.show_annotations else "hidden")
        if self.unchanged > 0:
            message += "\n{} internal annotations unchanged due to ownership by:".format(self.unchanged)
            for owner in sorted(self.unchanged_owners):
                message += "- {}\n".format(owner)
                
        NOTIFICATION.messenger(message)
        
    def execute(self):
        """Execute the annotation visibility handling process."""
        if not self.get_internal_annotations():
            NOTIFICATION.messenger("No internal annotations found in project.\nThe type name prefix used for searching is: [{}]".format(INTERNAL_TYPE_NAME_PREFIX))
            return
            
        show_annotations = self.get_user_choice()
        if show_annotations is None:
            return
            
        if not self.process_annotations():
            NOTIFICATION.messenger("No editable internal annotations found.")
            return
        
        self.modify_visibility(show_annotations)
        self.report_results()

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def handle_internal_annotation(doc):
    """Main function to handle internal annotations visibility."""
    handler = InternalAnnotationHandler(doc)
    handler.execute()

################## main code below #####################
if __name__ == "__main__":
    handle_internal_annotation(DOC)







