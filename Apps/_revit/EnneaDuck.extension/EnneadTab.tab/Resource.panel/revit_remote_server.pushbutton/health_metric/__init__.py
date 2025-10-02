import os
import sys
from Autodesk.Revit import DB # pyright: ignore
from datetime import datetime


def add_kingduck_lib_to_path():
    # Add the KingDuck.lib directory to sys.path to find proDUCKtion
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up to Apps/_revit/KingDuck.lib: health_metric -> revit_remote_server.pushbutton -> Resource.panel -> EnneadTab.tab -> EnneaDuck.extension -> _revit -> Apps -> _revit -> KingDuck.lib
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))))))
    kingduck_lib_dir = os.path.join(base_dir, "Apps", "_revit", "KingDuck.lib")
    sys.path.insert(0, kingduck_lib_dir)

add_kingduck_lib_to_path()
import proDUCKtion  # pyright: ignore
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
# No need for complex data holders - just return structured data

class HealthMetric:
    @LOG.log(__file__, __name__)
    @ERROR_HANDLE.try_catch_error()
    def __init__(self, doc):
        self.doc = doc
        self.report = {}
        self.report["is_EnneadTab_Available"] = True
        self.report["timestamp"] = datetime.now().isoformat()
        self.report["document_title"] = doc.Title

    def check(self):
        """Run comprehensive health metric collection"""
        self._check_project_info()
        self._check_linked_files()
        self._check_critical_elements()
        self._check_rooms()
        self._check_sheets_views()
        self._check_templates_filters()
        self._check_cad_files()
        self._check_families()
        self._check_graphical_elements()
        self._check_groups()
        self._check_reference_planes()
        self._check_materials()
        self._check_warnings()
        
        return self.report

    def _check_project_info(self):
        """Collect basic project information"""
        try:
            project_info = {}
            
            # Get project information
            project_data = self.doc.ProjectInformation
            if project_data:
                project_info["project_name"] = project_data.Name or "Unknown"
                project_info["project_number"] = project_data.Number or "Unknown"
                project_info["client_name"] = project_data.ClientName or "Unknown"
                project_info["project_phases"] = self._get_project_phases()
            else:
                project_info["project_name"] = "Unknown"
                project_info["project_number"] = "Unknown"
                project_info["client_name"] = "Unknown"
                project_info["project_phases"] = []
            
            # Check if workshared
            project_info["is_workshared"] = self.doc.IsWorkshared
            if self.doc.IsWorkshared:
                project_info["worksets"] = self._get_worksets_info()
            else:
                project_info["worksets"] = "Not Workshared"
            
            # Document title
            project_info["document_title"] = self.doc.Title
            
            # Check if EnneadTab is available
            project_info["is_EnneadTab_Available"] = self._check_enneadtab_availability()
            
            # Add timestamp
            project_info["timestamp"] = datetime.now().isoformat()
            
            self.report["project_info"] = project_info
            
        except Exception as e:
            self.report["project_info"] = {"error": str(e)}

    def _get_project_phases(self):
        """Get project phases information"""
        try:
            phases = []
            phase_collector = DB.FilteredElementCollector(self.doc).OfClass(DB.Phase)
            for phase in phase_collector:
                phases.append(phase.Name)
            return phases
        except:
            return []

    def _get_worksets_info(self):
        """Get comprehensive worksets information"""
        try:
            # Use FilteredWorksetCollector instead of GetWorksetIds - based on codebase patterns
            all_worksets = DB.FilteredWorksetCollector(self.doc).ToWorksets()
            worksets_data = {
                "total_worksets": 0,
                "user_worksets": 0,
                "system_worksets": 0,
                "workset_names": [],
                "workset_details": [],
                "workset_ownership": {},
                "workset_element_counts": {}
            }
            
            for workset in all_worksets:
                worksets_data["total_worksets"] += 1
                worksets_data["workset_names"].append(workset.Name)
                
                # Categorize worksets
                if workset.Kind == DB.WorksetKind.UserWorkset:
                    worksets_data["user_worksets"] += 1
                else:
                    worksets_data["system_worksets"] += 1
                
                # Get workset details
                workset_detail = {
                    "name": workset.Name,
                    "kind": str(workset.Kind),
                    "id": workset.Id.IntegerValue,
                    "is_open": workset.IsOpen,
                    "is_editable": workset.IsEditable,
                    "owner": workset.Owner if hasattr(workset, 'Owner') else "Unknown"
                }
                worksets_data["workset_details"].append(workset_detail)
                
                # Count elements in each workset
                try:
                    elements_in_workset = DB.FilteredElementCollector(self.doc).WherePasses(
                        DB.ElementWorksetFilter(workset.Id)
                    ).ToElements()
                    worksets_data["workset_element_counts"][workset.Name] = len(elements_in_workset)
                except Exception as e:
                    worksets_data["workset_element_counts"][workset.Name] = 0
                    
            return worksets_data
        except Exception as e:
            return {"error": str(e)}

    def _check_linked_files(self):
        """Check linked files information"""
        try:
            linked_files = []
            link_instances = DB.FilteredElementCollector(self.doc).OfClass(DB.RevitLinkInstance)
            
            for link in link_instances:
                link_doc = link.GetLinkDocument()
                if link_doc:
                    link_info = {
                        "linked_file_name": link_doc.Title,
                        "instance_name": link.Name,
                        "loaded_status": "Loaded" if link.IsHidden == False else "Hidden",
                        "pinned_status": "Pinned" if link.Pinned else "Unpinned"
                    }
                    linked_files.append(link_info)
            
            self.report["linked_files"] = linked_files
            self.report["linked_files_count"] = len(linked_files)
        except Exception as e:
            self.report["linked_files_error"] = str(e)

    def _check_critical_elements(self):
        """Check critical elements metrics"""
        try:
            # Total elements
            all_elements = DB.FilteredElementCollector(self.doc).WhereElementIsNotElementType().ToElements()
            self.report["total_elements"] = len(all_elements)
            
            # Purgeable elements (2024+ feature)
            try:
                purgeable_elements = DB.FilteredElementCollector(self.doc).WhereElementIsNotElementType().WherePasses(
                    DB.FilteredElementCollector(self.doc).OfClass(DB.Element).WherePasses(
                        DB.FilteredElementCollector(self.doc).OfClass(DB.ElementType)
                    )
                ).ToElements()
                self.report["purgeable_elements"] = len(purgeable_elements)
            except:
                self.report["purgeable_elements"] = 0
            
            # Warnings
            all_warnings = self.doc.GetWarnings()
            self.report["warning_count"] = len(all_warnings)
            
            # Critical warnings
            critical_warnings = [w for w in all_warnings if w.GetSeverity() == DB.FailureSeverity.Error]
            self.report["critical_warning_count"] = len(critical_warnings)
            

            
        except Exception as e:
            self.report["critical_elements_error"] = str(e)



    def _check_rooms(self):
        """Check rooms metrics"""
        try:
            rooms_data = {}
            
            rooms = DB.FilteredElementCollector(self.doc).OfCategory(DB.BuiltInCategory.OST_Rooms).WhereElementIsNotElementType().ToElements()
            rooms_data["total_rooms"] = len(rooms)
            
            unplaced_rooms = [r for r in rooms if r.Location is None]
            rooms_data["unplaced_rooms"] = len(unplaced_rooms)
            
            unbounded_rooms = [r for r in rooms if r.Area == 0]
            rooms_data["unbounded_rooms"] = len(unbounded_rooms)
            
            self.report["rooms"] = rooms_data
            
        except Exception as e:
            self.report["rooms"] = {"error": str(e)}

    def _check_sheets_views(self):
        """Check sheets and views metrics"""
        try:
            views_data = {}
            
            # Sheets
            sheets = DB.FilteredElementCollector(self.doc).OfClass(DB.ViewSheet).ToElements()
            views_data["total_sheets"] = len(sheets)
            
            # Views
            views = DB.FilteredElementCollector(self.doc).OfClass(DB.View).ToElements()
            views_data["total_views"] = len(views)
            
            # Views not on sheets
            views_not_on_sheets = [v for v in views if not isinstance(v, DB.ViewSheet) and v.CanBePrinted]
            views_data["views_not_on_sheets"] = len(views_not_on_sheets)
            
            # Schedules not on sheets
            schedules = DB.FilteredElementCollector(self.doc).OfClass(DB.ViewSchedule).ToElements()
            schedules_not_on_sheets = [s for s in schedules if s.CanBePrinted]
            views_data["schedules_not_on_sheets"] = len(schedules_not_on_sheets)
            
            # Copied views
            copied_views = [v for v in views if v.IsTemplate == False and hasattr(v, 'ViewTemplateId')]
            views_data["copied_views"] = len(copied_views)
            
            # View types
            view_types = {}
            for view in views:
                view_type = view.ViewType.ToString()
                if view_type not in view_types:
                    view_types[view_type] = 0
                view_types[view_type] += 1
            views_data["view_types"] = view_types
            
            self.report["views_sheets"] = views_data
            
        except Exception as e:
            self.report["views_sheets"] = {"error": str(e)}


    def _check_templates_filters(self):
        """Check templates and filters metrics"""
        try:
            templates_data = {}
            
            # View templates - based on QAQC_runner.py pattern
            all_views = DB.FilteredElementCollector(self.doc).OfClass(DB.View).ToElements()
            all_true_views = [v for v in all_views if v.IsTemplate == False]
            all_templates = [v for v in all_views if v.IsTemplate == True]
            
            templates_data["view_templates"] = len(all_templates)
            
            # Check for unused view templates - based on QAQC_runner.py pattern
            usage = {}
            for view in all_true_views:
                template = self.doc.GetElement(view.ViewTemplateId)
                if not template:
                    continue
                key = template.Name
                count = usage.get(key, 0)
                usage[key] = count + 1
            
            used_template_names = set(usage.keys())
            unused_templates = [x for x in all_templates if x.Name not in used_template_names]
            templates_data["unused_view_templates"] = len(unused_templates)
            
            # Filters
            filters = DB.FilteredElementCollector(self.doc).OfClass(DB.ParameterFilterElement).ToElements()
            templates_data["filters"] = len(filters)
            
            # Unused filters - check if filters are used in views
            used_filters = set()
            for view in all_true_views:
                try:
                    # Only check views that support filters (skip certain view types)
                    if hasattr(view, 'GetFilters'):
                        filter_ids = view.GetFilters()
                        if filter_ids:
                            for filter_id in filter_ids:
                                used_filters.add(filter_id.IntegerValue)
                except Exception as e:
                    # Skip views that don't support filters (like schedules, legends, etc.)
                    continue
            
            unused_filters = [f for f in filters if f.Id.IntegerValue not in used_filters]
            templates_data["unused_filters"] = len(unused_filters)
            
            self.report["templates_filters"] = templates_data
            
        except Exception as e:
            self.report["templates_filters"] = {"error": str(e)}

    def _check_cad_files(self):
        """Check CAD files metrics"""
        try:
            cad_data = {}
            
            # DWG files - based on QAQC_runner.py pattern
            all_dwgs = DB.FilteredElementCollector(self.doc).OfClass(DB.ImportInstance).WhereElementIsNotElementType().ToElements()
            
            # Imported DWGs (not linked)
            imported_dwgs = [x for x in all_dwgs if not x.IsLinked]
            cad_data["imported_dwgs"] = len(imported_dwgs)
            
            # Linked DWGs
            linked_dwgs = [x for x in all_dwgs if x.IsLinked]
            cad_data["linked_dwgs"] = len(linked_dwgs)
            
            # Total DWG files
            cad_data["dwg_files"] = len(all_dwgs)
            
            # CAD layers in families
            cad_layers_in_families = 0
            try:
                family_instances = DB.FilteredElementCollector(self.doc).OfClass(DB.FamilyInstance).ToElements()
                for fi in family_instances:
                    if hasattr(fi, 'GetParameters'):
                        for param in fi.GetParameters():
                            if param and param.AsString() and 'CAD' in param.AsString():
                                cad_layers_in_families += 1
            except:
                pass
            cad_data["cad_layers_imports_in_families"] = cad_layers_in_families
            
            self.report["cad_files"] = cad_data
            
        except Exception as e:
            self.report["cad_files"] = {"error": str(e)}

    def _check_families(self):
        """Check families metrics with advanced analysis"""
        try:
            families_data = {}
            
            # All families
            families = DB.FilteredElementCollector(self.doc).OfClass(DB.Family).ToElements()
            families_data["total_families"] = len(families)
            
            # In-place families
            in_place_families = [f for f in families if f.IsInPlace]
            families_data["in_place_families"] = len(in_place_families)
            
            # Non-parametric families
            non_parametric_families = [f for f in families if not f.IsParametric]
            families_data["non_parametric_families"] = len(non_parametric_families)
            
            # Generic models
            generic_models = DB.FilteredElementCollector(self.doc).OfClass(DB.FamilySymbol).ToElements()
            generic_models = [gm for gm in generic_models if gm.Category and "Generic Model" in gm.Category.Name]
            families_data["generic_models_types"] = len(generic_models)
            
            # Detail components
            detail_components = DB.FilteredElementCollector(self.doc).OfClass(DB.FamilySymbol).ToElements()
            detail_components = [dc for dc in detail_components if dc.Category and "Detail Component" in dc.Category.Name]
            families_data["detail_components"] = len(detail_components)
            
            # Advanced family analysis - based on QAQC_runner.py pattern
            families_data["in_place_families_creators"] = self._analyze_family_creators(in_place_families)
            families_data["non_parametric_families_creators"] = self._analyze_family_creators(non_parametric_families)
            
            self.report["families"] = families_data
            
        except Exception as e:
            self.report["families"] = {"error": str(e)}

    def _analyze_family_creators(self, families):
        """Analyze family creators - based on QAQC_runner.py pattern"""
        try:
            creator_data = {}
            for family in families:
                try:
                    creator = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, family.Id).Creator
                    count = creator_data.get(creator, 0)
                    creator_data[creator] = count + 1
                except:
                    pass  # Skip if worksharing info not available
            
            return creator_data
            
        except Exception as e:
            return {"error": str(e)}

    def _check_graphical_elements(self):
        """Check graphical 2D elements metrics"""
        try:
            # Detail lines - use CurveElement and filter for DetailCurve type
            curve_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.CurveElement).ToElements()
            detail_lines = [ce for ce in curve_elements if ce.CurveElementType.ToString() == "DetailCurve"]
            self.report["detail_lines"] = len(detail_lines)
            
            # Line patterns
            line_patterns = DB.FilteredElementCollector(self.doc).OfClass(DB.LinePatternElement).ToElements()
            self.report["line_patterns"] = len(line_patterns)
            
            # Text notes
            text_notes = DB.FilteredElementCollector(self.doc).OfClass(DB.TextNote).ToElements()
            self.report["text_notes_instances"] = len(text_notes)
            
            # Text note types
            text_note_types = DB.FilteredElementCollector(self.doc).OfClass(DB.TextNoteType).ToElements()
            self.report["text_notes_types"] = len(text_note_types)
            
            # Text notes with solid background
            solid_background_notes = [tn for tn in text_note_types if hasattr(tn, 'Background') and tn.Background == DB.TextNoteBackground.Solid]
            self.report["text_notes_types_solid_background"] = len(solid_background_notes)
            
            # Text notes width factor != 1
            width_factor_notes = [tn for tn in text_note_types if hasattr(tn, 'WidthFactor') and tn.WidthFactor != 1.0]
            self.report["text_notes_width_factor_not_1"] = len(width_factor_notes)
            
            # Text notes all caps
            all_caps_notes = [tn for tn in text_note_types if hasattr(tn, 'AllCaps') and tn.AllCaps]
            self.report["text_notes_all_caps"] = len(all_caps_notes)
            
            # Dimensions
            dimensions = DB.FilteredElementCollector(self.doc).OfClass(DB.Dimension).ToElements()
            self.report["dimensions"] = len(dimensions)
            
            # Dimension types
            dimension_types = DB.FilteredElementCollector(self.doc).OfClass(DB.DimensionType).ToElements()
            self.report["dimension_types"] = len(dimension_types)
            
            # Dimension overrides
            dimension_overrides = [d for d in dimensions if d.ValueOverride != ""]
            self.report["dimension_overrides"] = len(dimension_overrides)
            
            # Revision clouds
            revision_clouds = DB.FilteredElementCollector(self.doc).OfClass(DB.RevisionCloud).ToElements()
            self.report["revision_clouds"] = len(revision_clouds)
            
        except Exception as e:
            self.report["graphical_elements_error"] = str(e)

    def _check_groups(self):
        """Check groups metrics with usage analysis"""
        try:
            # Model groups
            model_groups = DB.FilteredElementCollector(self.doc).OfClass(DB.Group).ToElements()
            self.report["model_group_instances"] = len(model_groups)
            
            # Model group types
            model_group_types = DB.FilteredElementCollector(self.doc).OfClass(DB.GroupType).ToElements()
            self.report["model_group_types"] = len(model_group_types)
            
            # Detail groups - use category instead of class
            detail_groups = DB.FilteredElementCollector(self.doc).OfCategory(DB.BuiltInCategory.OST_IOSDetailGroups).WhereElementIsNotElementType().ToElements()
            self.report["detail_group_instances"] = len(detail_groups)
            
            # Detail group types
            detail_group_types = DB.FilteredElementCollector(self.doc).OfCategory(DB.BuiltInCategory.OST_IOSDetailGroups).WhereElementIsElementType().ToElements()
            self.report["detail_group_types"] = len(detail_group_types)
            
            # Advanced group usage analysis - based on QAQC_runner.py pattern
            self._analyze_group_usage(model_groups, "model_group")
            self._analyze_group_usage(detail_groups, "detail_group")
            
        except Exception as e:
            self.report["groups_error"] = str(e)

    def _analyze_group_usage(self, groups, group_type):
        """Analyze group usage patterns - based on QAQC_runner.py pattern"""
        try:
            type_data = {}
            for group in groups:
                type_name = group.Name
                current_count = type_data.get(type_name, 0)
                type_data[type_name] = current_count + 1
            
            # Flag groups used more than 10 times - based on QAQC_runner.py threshold
            threshold = 10
            overused_groups = [type_name for type_name, count in type_data.items() if count > threshold]
            
            self.report["{}_usage_analysis".format(group_type)] = {
                "total_types": len(type_data),
                "overused_count": len(overused_groups),
                "overused_groups": overused_groups,
                "usage_threshold": threshold,
                "type_usage": type_data
            }
            
        except Exception as e:
            self.report["{}_usage_analysis_error".format(group_type)] = str(e)

    def _check_reference_planes(self):
        """Check reference planes metrics"""
        try:
            # Reference planes - based on QAQC_runner.py pattern
            all_ref_planes = DB.FilteredElementCollector(self.doc).OfClass(DB.ReferencePlane).ToElements()
            # Only get ref planes whose workset is not read-only (project refs, not family refs)
            # Handle NoneType error by checking if LookupParameter returns None
            ref_planes = []
            for rp in all_ref_planes:
                try:
                    workset_param = rp.LookupParameter("Workset")
                    if workset_param and not workset_param.IsReadOnly:
                        ref_planes.append(rp)
                except:
                    # If we can't check workset, include it (safer approach)
                    ref_planes.append(rp)
            
            self.report["reference_planes"] = len(ref_planes)
            
            # Unnamed reference planes - based on QAQC_runner.py pattern
            # Check for default "Reference Plane" name and empty/whitespace names
            unnamed_ref_planes = [rp for rp in ref_planes if 
                                 rp.Name == "Reference Plane" or 
                                 not rp.Name or 
                                 rp.Name.strip() == ""]
            self.report["reference_planes_no_name"] = len(unnamed_ref_planes)
            
        except Exception as e:
            self.report["reference_planes_error"] = str(e)

    def _check_materials(self):
        """Check materials count"""
        try:
            materials = DB.FilteredElementCollector(self.doc).OfClass(DB.Material).ToElements()
            self.report["materials"] = len(materials)
        except Exception as e:
            self.report["materials_error"] = str(e)

    def _check_warnings(self):
        """Check warnings metrics with advanced analysis"""
        try:
            warnings_data = {}
            
            # Warnings - based on QAQC_runner.py pattern
            all_warnings = self.doc.GetWarnings()
            warnings_data["warning_count"] = len(all_warnings)
            
            # Critical warnings - based on QAQC_runner.py pattern
            CRITICAL_WARNINGS = [
                "6e1efefe-c8e0-483d-8482-150b9f1da21a",  # Elements have duplicate "Number" values
                "b4176cef-6086-45a8-a066-c3fd424c9412",  # There are identical instances in the same place
                "4f0bba25-e17f-480a-a763-d97d184be18a",  # Room Tag is outside of its Room
                "505d84a1-67e4-4987-8287-21ad1792ffe9",  # One element is completely inside another
                "8695a52f-2a88-4ca2-bedc-3676d5857af6",  # Highlighted floors overlap
                "ce3275c6-1c51-402e-8de3-df3a3d566f5c",  # Room is not in a properly enclosed region
                "83d4a67c-818c-4291-adaf-f2d33064fea8",  # Multiple Rooms are in the same enclosed region
                "e4d98f16-24ac-4cbe-9d83-80245cf41f0a",  # Area is not in a properly enclosed region
                "f657364a-e0b7-46aa-8c17-edd8e59683b9",  # Multiple Areas are in the same enclosed region
            ]
            
            critical_warnings = [w for w in all_warnings if w.GetFailureDefinitionId().Guid in CRITICAL_WARNINGS]
            warnings_data["critical_warning_count"] = len(critical_warnings)
            
            # Advanced warning analysis - based on QAQC_runner.py patterns
            warning_category = {}
            user_personal_log = {}
            failed_elements = []
            
            for warning in all_warnings:
                warning_text = warning.GetDescriptionText()
                
                # Update warning category count
                current_count = warning_category.get(warning_text, 0)
                warning_category[warning_text] = current_count + 1
                
                # Collect failing elements
                failed_elements.extend(list(warning.GetFailingElements()))
                
                # Process creator information - based on QAQC_runner.py pattern
                try:
                    creators = [DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, x).Creator for x in warning.GetFailingElements()]
                    
                    for creator in creators:
                        if creator not in user_personal_log:
                            user_personal_log[creator] = {}
                            
                        current_log = user_personal_log[creator]
                        current_log[warning_text] = current_log.get(warning_text, 0) + 1
                except:
                    pass  # Skip if worksharing info not available
            
            # Store advanced warning analysis
            warnings_data["warning_categories"] = warning_category
            warnings_data["warning_count_per_user"] = self._get_user_element_counts(failed_elements)
            warnings_data["warning_details_per_user"] = user_personal_log
            
            self.report["warnings"] = warnings_data
            
        except Exception as e:
            self.report["warnings"] = {"error": str(e)}

    def _get_user_element_counts(self, elements):
        """Get element counts per user - based on QAQC_runner.py pattern"""
        try:
            user_data = {}
            for element in elements:
                try:
                    creator = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, element.Id).Creator
                    count = user_data.get(creator, 0)
                    user_data[creator] = count + 1
                except:
                    pass  # Skip if worksharing info not available
            return user_data
        except:
            return {}

    def _check_enneadtab_availability(self):
        """Check if EnneadTab is available in the current session"""
        try:
            # Try to import EnneadTab modules to check availability
            import sys
            enneadtab_paths = [p for p in sys.path if 'EnneadTab' in p or 'EnneaDuck' in p]
            return len(enneadtab_paths) > 0
        except:
            return False
