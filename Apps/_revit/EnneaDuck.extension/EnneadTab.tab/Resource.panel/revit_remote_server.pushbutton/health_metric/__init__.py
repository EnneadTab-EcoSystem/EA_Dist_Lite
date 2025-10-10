import traceback
from Autodesk.Revit import DB # pyright: ignore
from datetime import datetime

# STANDALONE VERSION - No EnneadTab or proDUCKtion dependencies
# This makes the HealthMetric completely independent and faster to import

class HealthMetric:
    def __init__(self, doc):
        self.doc = doc
        self.report = {}
        self.report["is_EnneadTab_Available"] = False  # Standalone version
        self.report["timestamp"] = datetime.now().isoformat()
        self.report["document_title"] = doc.Title

    def check(self):
        """Run comprehensive health metric collection with progress logging"""
        try:
            print("STATUS: Starting project info collection...")
            self._check_project_info()
            print("STATUS: Project info completed, checking linked files...")
            self._check_linked_files()
            print("STATUS: Linked files completed, checking critical elements...")
            self._check_critical_elements()
            print("STATUS: Critical elements completed, checking rooms...")
            self._check_rooms()
            print("STATUS: Rooms completed, checking sheets/views...")
            self._check_sheets_views()
            print("STATUS: Sheets/views completed, checking templates/filters...")
            self._check_templates_filters()
            print("STATUS: Templates/filters completed, checking CAD files...")
            self._check_cad_files()
            print("STATUS: CAD files completed, checking families...")
            self._check_families()
            print("STATUS: Families completed, checking graphical elements...")
            self._check_graphical_elements()
            print("STATUS: Graphical elements completed, checking groups...")
            self._check_groups()
            print("STATUS: Groups completed, checking reference planes...")
            self._check_reference_planes()
            print("STATUS: Reference planes completed, checking materials...")
            self._check_materials()
            print("STATUS: Materials completed, checking line counts...")
            self._check_line_count()
            print("STATUS: Line counts completed, checking warnings...")
            self._check_warnings()
            print("STATUS: All health metric checks completed successfully!")
            
            return self.report
        except Exception as e:
            print("STATUS: HealthMetric failed at: {}".format(str(e)))
            # Add error to report and return partial results
            self.report["health_metric_error"] = str(traceback.format_exc())
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
        """Get comprehensive worksets information - limited to user worksets only"""
        try:
            # Use FilteredWorksetCollector instead of GetWorksetIds - based on codebase patterns
            all_worksets = DB.FilteredWorksetCollector(self.doc).ToWorksets()
            
            # Filter to user worksets only
            user_worksets = [ws for ws in all_worksets if ws.Kind == DB.WorksetKind.UserWorkset]
            
            worksets_data = {
                "total_worksets": len(user_worksets),
                "user_worksets": len(user_worksets),
                "workset_names": [],
                "workset_details": [],
                "workset_ownership": {},
                "workset_element_counts": {},
                "workset_element_ownership": {}
            }
            
            # Only process user worksets
            for workset in user_worksets:
                worksets_data["workset_names"].append(workset.Name)
                
                # Get workset details
                workset_detail = {
                    "name": workset.Name,
                    "kind": str(workset.Kind),
                    "id": workset.Id.IntegerValue,
                    "is_open": workset.IsOpen,
                    "is_editable": workset.IsEditable,
                    "owner": workset.Owner if hasattr(workset, 'Owner') else "Unknown",
                    "creator": "Unknown",
                    "last_editor": "Unknown"
                }
                
                # Try to get creator and last editor for the workset
                # Note: Worksets are not elements, so we derive this from elements in the workset
                try:
                    # Get elements in the workset to derive ownership info
                    elements_in_workset = DB.FilteredElementCollector(self.doc).WherePasses(
                        DB.ElementWorksetFilter(workset.Id)
                    ).ToElements()
                    
                    if elements_in_workset:
                        # Collect ownership info from elements in this workset
                        creators = {}
                        last_editors = {}
                        current_owners = {}
                        
                        for element in elements_in_workset[:100]:  # Sample first 100 elements for performance
                            try:
                                info = DB.WorksharingUtils.GetWorksharingTooltipInfo(self.doc, element.Id)
                                if info:
                                    creator = info.Creator
                                    last_editor = info.LastChangedBy
                                    owner = info.Owner
                                    
                                    if creator:
                                        creators[creator] = creators.get(creator, 0) + 1
                                    if last_editor:
                                        last_editors[last_editor] = last_editors.get(last_editor, 0) + 1
                                    if owner:
                                        current_owners[owner] = current_owners.get(owner, 0) + 1
                            except:
                                continue
                        
                        # Store ownership statistics for this workset (detailed breakdown)
                        worksets_data["workset_element_ownership"][workset.Name] = {
                            "creators": creators,
                            "last_editors": last_editors,
                            "current_owners": current_owners
                        }
                        
                        # Set the most common creator/editor as workset's primary creator/editor
                        # These represent the dominant contributor to this workset
                        if creators:
                            workset_detail["creator"] = max(creators.items(), key=lambda x: x[1])[0]
                            workset_detail["creator_count"] = creators[workset_detail["creator"]]
                        if last_editors:
                            workset_detail["last_editor"] = max(last_editors.items(), key=lambda x: x[1])[0]
                            workset_detail["last_editor_count"] = last_editors[workset_detail["last_editor"]]
                        
                    worksets_data["workset_element_counts"][workset.Name] = len(elements_in_workset)
                    
                except Exception as e:
                    worksets_data["workset_element_counts"][workset.Name] = 0
                    worksets_data["workset_element_ownership"][workset.Name] = {
                        "error": str(e)
                    }
                
                worksets_data["workset_details"].append(workset_detail)
                    
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
            
            # Warnings with detailed element information
            all_warnings = self.doc.GetWarnings()
            self.report["warning_count"] = len(all_warnings)
            
            # Collect detailed warning information
            warning_details = []
            warning_creators = {}
            warning_last_editors = {}
            
            for warning in all_warnings:
                try:
                    warning_info = {
                        "description": warning.GetDescriptionText(),
                        "severity": str(warning.GetSeverity()),
                        "element_ids": [],
                        "elements_info": []
                    }
                    
                    # Get element IDs involved in the warning
                    element_ids = warning.GetFailingElements()
                    if element_ids:
                        for elem_id in element_ids:
                            try:
                                warning_info["element_ids"].append(elem_id.IntegerValue)
                                
                                # Get element and its creator/last editor
                                element = self.doc.GetElement(elem_id)
                                if element:
                                    elem_info = {
                                        "id": elem_id.IntegerValue,
                                        "category": element.Category.Name if element.Category else "Unknown",
                                        "creator": "Unknown",
                                        "last_editor": "Unknown"
                                    }
                                    
                                    # Get worksharing info
                                    try:
                                        info = DB.WorksharingUtils.GetWorksharingTooltipInfo(self.doc, elem_id)
                                        if info:
                                            if info.Creator:
                                                elem_info["creator"] = info.Creator
                                                count = warning_creators.get(info.Creator, 0)
                                                warning_creators[info.Creator] = count + 1
                                            if info.LastChangedBy:
                                                elem_info["last_editor"] = info.LastChangedBy
                                                count = warning_last_editors.get(info.LastChangedBy, 0)
                                                warning_last_editors[info.LastChangedBy] = count + 1
                                    except:
                                        pass  # Skip if worksharing info not available
                                    
                                    warning_info["elements_info"].append(elem_info)
                            except:
                                continue
                    
                    warning_details.append(warning_info)
                except Exception as e:
                    # Skip warnings that fail to process
                    continue
            
            self.report["warning_details"] = warning_details[:100]  # Limit to 100 warnings for performance
            self.report["warning_creators"] = warning_creators
            self.report["warning_last_editors"] = warning_last_editors
            
            # Critical warnings
            critical_warnings = [w for w in all_warnings if w.GetSeverity() == DB.FailureSeverity.Error]
            self.report["critical_warning_count"] = len(critical_warnings)
            
            # Critical warning details
            critical_warning_details = []
            for warning in critical_warnings[:50]:  # Limit to 50 critical warnings
                try:
                    critical_info = {
                        "description": warning.GetDescriptionText(),
                        "element_ids": [e.IntegerValue for e in warning.GetFailingElements()]
                    }
                    critical_warning_details.append(critical_info)
                except:
                    continue
            
            self.report["critical_warning_details"] = critical_warning_details

            
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
            
            # View count by view type - comprehensive breakdown
            view_count_by_type = {}
            view_count_by_type_non_template = {}
            view_count_by_type_template = {}
            
            for view in views:
                view_type = view.ViewType.ToString()
                
                # Overall count
                current_count = view_count_by_type.get(view_type, 0)
                view_count_by_type[view_type] = current_count + 1
                
                # Separate templates from non-templates
                if view.IsTemplate:
                    current_template_count = view_count_by_type_template.get(view_type, 0)
                    view_count_by_type_template[view_type] = current_template_count + 1
                else:
                    current_non_template_count = view_count_by_type_non_template.get(view_type, 0)
                    view_count_by_type_non_template[view_type] = current_non_template_count + 1
            
            views_data["view_count_by_type"] = view_count_by_type
            views_data["view_count_by_type_non_template"] = view_count_by_type_non_template
            views_data["view_count_by_type_template"] = view_count_by_type_template
            
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
            
            # Collect detailed view template information with creator and last editor
            template_details = []
            for template in all_templates:
                try:
                    template_info = {
                        "name": template.Name,
                        "id": template.Id.IntegerValue,
                        "view_type": str(template.ViewType) if hasattr(template, 'ViewType') else "Unknown",
                        "is_used": template.Name in used_template_names,
                        "usage_count": usage.get(template.Name, 0),
                        "creator": "Unknown",
                        "last_editor": "Unknown"
                    }
                    
                    # Get creator and last editor from WorksharingUtils
                    try:
                        info = DB.WorksharingUtils.GetWorksharingTooltipInfo(self.doc, template.Id)
                        if info:
                            if info.Creator:
                                template_info["creator"] = info.Creator
                            if info.LastChangedBy:
                                template_info["last_editor"] = info.LastChangedBy
                    except:
                        pass  # Skip if worksharing info not available
                    
                    template_details.append(template_info)
                except Exception as e:
                    # Skip templates that fail
                    continue
            
            templates_data["view_template_details"] = template_details
            
            # Add creator and last editor statistics
            templates_data["view_template_creators"] = self._analyze_template_creators(all_templates)
            templates_data["unused_view_template_details"] = [
                {
                    "name": t.Name,
                    "id": t.Id.IntegerValue,
                    "view_type": str(t.ViewType) if hasattr(t, 'ViewType') else "Unknown"
                }
                for t in unused_templates
            ]
            
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
            
            # Find unused families
            unused_families_info = self._find_unused_families(families)
            families_data["unused_families_count"] = unused_families_info["count"]
            families_data["unused_families_names"] = unused_families_info["names"]
            
            # Advanced family analysis - based on QAQC_runner.py pattern
            families_data["in_place_families_creators"] = self._analyze_family_creators(in_place_families)
            families_data["non_parametric_families_creators"] = self._analyze_family_creators(non_parametric_families)
            
            self.report["families"] = families_data
            
        except Exception as e:
            self.report["families"] = {"error": str(e)}

    def _analyze_family_creators(self, families):
        """Analyze family creators and last editors - based on QAQC_runner.py pattern"""
        try:
            creator_data = {}
            last_editor_data = {}
            for family in families:
                try:
                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, family.Id)
                    if info:
                        creator = info.Creator
                        last_editor = info.LastChangedBy
                        
                        if creator:
                            count = creator_data.get(creator, 0)
                            creator_data[creator] = count + 1
                        
                        if last_editor:
                            count = last_editor_data.get(last_editor, 0)
                            last_editor_data[last_editor] = count + 1
                except:
                    pass  # Skip if worksharing info not available
            
            return {
                "creators": creator_data,
                "last_editors": last_editor_data
            }
            
        except Exception as e:
            return {"error": str(e)}

    def _analyze_template_creators(self, templates):
        """Analyze view template creators and last editors"""
        try:
            creator_data = {}
            last_editor_data = {}
            for template in templates:
                try:
                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, template.Id)
                    if info:
                        creator = info.Creator
                        last_editor = info.LastChangedBy
                        
                        if creator:
                            count = creator_data.get(creator, 0)
                            creator_data[creator] = count + 1
                        
                        if last_editor:
                            count = last_editor_data.get(last_editor, 0)
                            last_editor_data[last_editor] = count + 1
                except:
                    pass  # Skip if worksharing info not available
            
            return {
                "creators": creator_data,
                "last_editors": last_editor_data
            }
            
        except Exception as e:
            return {"error": str(e)}

    def _find_unused_families(self, families):
        """Find families that have no instances placed in the project"""
        try:
            # Get all family instances in the project
            all_family_instances = DB.FilteredElementCollector(self.doc).OfClass(DB.FamilyInstance).ToElements()
            
            # Create a set of family IDs that are actually used
            used_family_ids = set()
            for instance in all_family_instances:
                try:
                    # Get the symbol (type) of this instance
                    symbol = instance.Symbol
                    if symbol:
                        # Get the family from the symbol
                        family = symbol.Family
                        if family:
                            used_family_ids.add(family.Id.IntegerValue)
                except:
                    continue
            
            # Find unused families
            unused_families = []
            for family in families:
                if family.Id.IntegerValue not in used_family_ids:
                    # Skip in-place families as they're special cases
                    if not family.IsInPlace:
                        unused_families.append(family.Name)
            
            return {
                "count": len(unused_families),
                "names": sorted(unused_families)
            }
            
        except Exception as e:
            return {
                "count": 0,
                "names": [],
                "error": str(e)
            }

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

    def _check_line_count(self):
        """Check detail and model line usage with per-view breakdown"""
        try:
            line_data = {}
            
            # Collect all curve elements
            curve_elements = DB.FilteredElementCollector(self.doc).OfClass(DB.CurveElement).ToElements()
            
            # Separate detail lines and model lines
            detail_lines = []
            model_lines = []
            
            for ce in curve_elements:
                curve_type = ce.CurveElementType.ToString()
                if curve_type == "DetailCurve":
                    detail_lines.append(ce)
                elif curve_type == "ModelCurve":
                    model_lines.append(ce)
            
            # Total counts
            line_data["detail_lines_total"] = len(detail_lines)
            line_data["model_lines_total"] = len(model_lines)
            
            # Detail lines per view
            detail_lines_per_view = {}
            for detail_line in detail_lines:
                try:
                    # Get the view that owns this detail line
                    owner_view_id = detail_line.OwnerViewId
                    if owner_view_id and owner_view_id != DB.ElementId.InvalidElementId:
                        view = self.doc.GetElement(owner_view_id)
                        if view:
                            view_name = view.Name
                            current_count = detail_lines_per_view.get(view_name, 0)
                            detail_lines_per_view[view_name] = current_count + 1
                except Exception as e:
                    # Skip if we can't get the view
                    continue
            
            line_data["detail_lines_per_view"] = detail_lines_per_view
            
            self.report["line_count"] = line_data
            
        except Exception as e:
            self.report["line_count_error"] = str(e)

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
            user_editor_log = {}
            failed_elements = []
            
            for warning in all_warnings:
                warning_text = warning.GetDescriptionText()
                
                # Update warning category count
                current_count = warning_category.get(warning_text, 0)
                warning_category[warning_text] = current_count + 1
                
                # Collect failing elements
                failed_elements.extend(list(warning.GetFailingElements()))
                
                # Process creator and last editor information - based on QAQC_runner.py pattern
                try:
                    failing_elements = warning.GetFailingElements()
                    for element_id in failing_elements:
                        info = DB.WorksharingUtils.GetWorksharingTooltipInfo(self.doc, element_id)
                        if info:
                            creator = info.Creator
                            last_editor = info.LastChangedBy
                            
                            # Track creator warnings
                            if creator:
                                if creator not in user_personal_log:
                                    user_personal_log[creator] = {}
                                current_log = user_personal_log[creator]
                                current_log[warning_text] = current_log.get(warning_text, 0) + 1
                            
                            # Track last editor warnings
                            if last_editor:
                                if last_editor not in user_editor_log:
                                    user_editor_log[last_editor] = {}
                                current_log = user_editor_log[last_editor]
                                current_log[warning_text] = current_log.get(warning_text, 0) + 1
                except:
                    pass  # Skip if worksharing info not available
            
            # Store advanced warning analysis
            warnings_data["warning_categories"] = warning_category
            warnings_data["warning_count_per_user"] = self._get_user_element_counts(failed_elements)
            warnings_data["warning_details_per_creator"] = user_personal_log
            warnings_data["warning_details_per_last_editor"] = user_editor_log
            
            self.report["warnings"] = warnings_data
            
        except Exception as e:
            self.report["warnings"] = {"error": str(e)}

    def _get_user_element_counts(self, elements):
        """Get element counts per user (creator and last editor) - based on QAQC_runner.py pattern"""
        try:
            creator_data = {}
            last_editor_data = {}
            for element in elements:
                try:
                    info = DB.WorksharingUtils.GetWorksharingTooltipInfo(
                        self.doc, element.Id)
                    if info:
                        creator = info.Creator
                        last_editor = info.LastChangedBy
                        
                        if creator:
                            count = creator_data.get(creator, 0)
                            creator_data[creator] = count + 1
                        
                        if last_editor:
                            count = last_editor_data.get(last_editor, 0)
                            last_editor_data[last_editor] = count + 1
                except:
                    pass  # Skip if worksharing info not available
            return {
                "by_creator": creator_data,
                "by_last_editor": last_editor_data
            }
        except:
            return {}

    def _check_enneadtab_availability(self):
        """Check if EnneadTab is available in the current session"""
        return False  # Standalone version doesn't use EnneadTab
