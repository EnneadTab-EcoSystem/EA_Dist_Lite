import traceback
from datetime import datetime

# STANDALONE VERSION - No EnneadTab or proDUCKtion dependencies
# This makes the HealthMetric completely independent and faster to import

# Import all check modules
from . import project_checks
from . import linked_files_checks
from . import elements_checks
from . import views_checks
from . import templates_checks
from . import cad_checks
from . import families_checks
from . import graphical_checks
from . import groups_checks
from . import reference_checks
from . import materials_checks
from . import warnings_checks
from . import file_checks
from . import regions_checks


class HealthMetric:
    def __init__(self, doc):
        self.doc = doc
        self.report = {
            "version": "v2",
            "timestamp": datetime.now().isoformat(),
            "document_title": doc.Title,
            "is_EnneadTab_Available": False,  # Standalone version
            "checks": {}
        }

    def check(self):
        """Run comprehensive health metric collection with progress logging"""
        try:
            print("STATUS: Starting project info collection...")
            self.report["checks"]["project_info"] = project_checks.check_project_info(self.doc)
            
            print("STATUS: Project info completed, checking linked files...")
            self.report["checks"]["linked_files"] = linked_files_checks.check_linked_files(self.doc)
            
            print("STATUS: Linked files completed, checking critical elements...")
            self.report["checks"]["critical_elements"] = elements_checks.check_critical_elements(self.doc)
            
            print("STATUS: Critical elements completed, checking rooms...")
            self.report["checks"]["rooms"] = elements_checks.check_rooms(self.doc)
            
            print("STATUS: Rooms completed, checking sheets/views...")
            self.report["checks"]["views_sheets"] = views_checks.check_sheets_views(self.doc)
            
            print("STATUS: Sheets/views completed, checking templates/filters...")
            self.report["checks"]["templates_filters"] = templates_checks.check_templates_filters(self.doc)
            
            print("STATUS: Templates/filters completed, checking CAD files...")
            self.report["checks"]["cad_files"] = cad_checks.check_cad_files(self.doc)
            
            print("STATUS: CAD files completed, checking families...")
            self.report["checks"]["families"] = families_checks.check_families(self.doc)
            
            print("STATUS: Families completed, checking graphical elements...")
            self.report["checks"]["graphical_elements"] = graphical_checks.check_graphical_elements(self.doc)
            
            print("STATUS: Graphical elements completed, checking groups...")
            self.report["checks"]["groups"] = groups_checks.check_groups(self.doc)
            
            print("STATUS: Groups completed, checking reference planes...")
            self.report["checks"]["reference_planes"] = reference_checks.check_reference_planes(self.doc)
            
            print("STATUS: Reference planes completed, checking materials...")
            self.report["checks"]["materials"] = materials_checks.check_materials(self.doc)
            
            print("STATUS: Materials completed, checking line counts...")
            self.report["checks"]["line_count"] = materials_checks.check_line_count(self.doc)
            
            print("STATUS: Line counts completed, checking warnings...")
            self.report["checks"]["warnings"] = warnings_checks.check_warnings(self.doc)
            
            print("STATUS: Warnings completed, checking file size...")
            self.report["checks"]["file_size"] = file_checks.check_file_size(self.doc)
            
            print("STATUS: File size completed, checking filled regions...")
            self.report["checks"]["filled_regions"] = regions_checks.check_filled_regions(self.doc)
            
            print("STATUS: Filled regions completed, checking grids/levels...")
            self.report["checks"]["grids_levels"] = reference_checks.check_grids_levels(self.doc)
            
            print("STATUS: All health metric checks completed successfully!")
            
            return self.report
        except Exception as e:
            print("STATUS: HealthMetric failed at: {}".format(str(e)))
            # Add error to report and return partial results
            self.report["error"] = str(traceback.format_exc())
            return self.report
