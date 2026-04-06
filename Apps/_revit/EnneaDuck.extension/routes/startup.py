# -*- coding: utf-8 -*-
"""EnneadTab MCP pyRevit Routes entry point.

Creates the API instance and imports all route modules.
"""
from pyrevit import routes

api = routes.API("enneadtab")

from status import register_status_routes
from model_info import register_model_info_routes
from elements import register_element_routes
from element_params import register_element_params_routes
from levels import register_level_routes
from views import register_view_routes
from families import register_family_routes
from element_set_param import register_element_set_param_routes
from execute_code import register_execute_code_routes
from view_image import register_view_image_routes
from create_sheet import register_create_sheet_routes
from create_view import register_create_view_routes
from place_family import register_place_family_routes
from sync import register_sync_routes
from enneadtab_tools import register_enneadtab_tools_routes

register_status_routes(api)
register_model_info_routes(api)
register_element_routes(api)
register_element_params_routes(api)
register_level_routes(api)
register_view_routes(api)
register_family_routes(api)
register_element_set_param_routes(api)
register_execute_code_routes(api)
register_view_image_routes(api)
register_create_sheet_routes(api)
register_create_view_routes(api)
register_place_family_routes(api)
register_sync_routes(api)
register_enneadtab_tools_routes(api)
