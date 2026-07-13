#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Export the object style and material table so Rhino can match layers to materials.

Feeds the Map Revit SubC tool in EnneadTab for Rhino: once this table exists,
each Rhino layer can be given the Revit material that belongs to the matching
subcategory, and the two models finally agree on what is made of what.

If you have not done it yet, update the DWG export layer mapping with EnneadTab
first, so subcategory names come out in a shape Rhino layer names can match."""
__title__ = "Export SubCategory\nMaterial Table"
__tip__ = True
# from pyrevit import forms #
import pprint
from pyrevit import script #

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from  EnneadTab import NOTIFICATION, DATA_FILE, ERROR_HANDLE, LOG
from EnneadTab.REVIT import REVIT_APPLICATION

from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()


class Solution:
    def __init__(self):
        self.table = dict()
        
    def process_category(self, category):
        if "Imports in Families" in category.Name or ".dwg" in category.Name.lower():
            return
        if category.Parent:
            if "Imports in Families" in category.Parent.Name or ".dwg" in category.Parent.Name.lower():
                return    

        if category.Material is None:
            # self.table[layer_name] = material_data
            return
        
        
        if category.Parent:
            layer_name = "{}_{}".format(category.Parent.Name, category.Name)
        else:
            layer_name = "{}".format(category.Name)
            


        material_data = dict()
        material = category.Material
        material_data["shading"] = {"name": material.Name,
                                    "color": {"red": int(material.Color.Red), "green": int(material.Color.Green), "blue": int(material.Color.Blue)},                      
                                    "transparency": material.Transparency,
                                    "glossy": material.Shininess ,
                                    "smoothness": material.Smoothness}
        
        apperance_asset = doc.GetElement(material.AppearanceAssetId)
        # print apperance_asset
        # for para in apperance_asset.Parameters:
        #     print para.Definition.Name
        # material_data["appearance"] = {"name": apperance_asset.Name,
        #                                "color": apperance_asset.Color.ToArgb(), 
        #                                 "transparency": apperance_asset.Transparency}
        
        # print (material_data)
        self.table[layer_name] = material_data
        
        
    def export_ost_material_table(self):
        
        categories = doc.Settings.Categories
        for i, category in enumerate(categories):

            self.process_category(category)
            
            for sub_c in category.SubCategories:
                self.process_category(sub_c)
        

        DATA_FILE.pretty_print_dict (self.table)
        # pprint.pprint(self.table, indent=4)
        DATA_FILE.set_data(self.table, "SUBC_MATERIAL_TABLE")
        NOTIFICATION.messenger("Export done, now swicth to 'map Revit SubC' in Rhino")



@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    Solution().export_ost_material_table()
    

################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    main()
    







