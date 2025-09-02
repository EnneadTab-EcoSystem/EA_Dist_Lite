#!/usr/bin/python
# -*- coding: utf-8 -*-

"""Template management classes for Area2Mass conversion."""

from EnneadTab import SAMPLE_FILE


class TemplateFinder:
    """Finds and validates mass family templates."""
    
    def get_mass_family_template(self):
        """Get the mass family template path."""
        try:
            # Use EmptyMass.rfa as the base family template
            template_filename = "EmptyMass.rfa"
            template_path = SAMPLE_FILE.get_file(template_filename)
            
            if not template_path:
                # Fallback: try to find any available mass template
                template_filename = "Mass.rft"
                template_path = SAMPLE_FILE.get_file(template_filename)
            
            if not template_path:
                # Final fallback: use generic model template
                template_filename = "Generic Model.rft"
                template_path = SAMPLE_FILE.get_file(template_filename)
            
            return template_path
            
        except Exception as e:
            print("Error getting mass family template: {}".format(str(e)))
            return None
