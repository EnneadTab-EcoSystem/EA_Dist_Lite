#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Turn surfaces drawn in Rhino into placed Revit adaptive components.

Pick the adaptive family and type to use, and each incoming surface is built from
its corner points. Set the corner order in Rhino first so the adaptive points
land where you expect them to.

Usage:
1. In Rhino, set the adaptive corner sequence and export the surfaces
2. Run this button, pick the family and type, and confirm the file unit"""
__title__ = "Srf2Adp"
__tip__ = True
from pyrevit import forms #
from pyrevit import script #

import traceback

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_UNIT, REVIT_SELECTION, REVIT_APPLICATION
from EnneadTab import SOUND, DATA_FILE, FOLDER, ERROR_HANDLE, LOG
from Autodesk.Revit import DB # pyright: ignore 
# from Autodesk.Revit import UI # pyright: ignore
# uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()
app = REVIT_APPLICATION.get_app()





class Solution:
    def __init__(self):
        family = REVIT_SELECTION.pick_family(doc)
        if family is None:
            return
        self.type = REVIT_SELECTION.pick_type(family)
        if self.type is None:
            return

        self.unit = REVIT_UNIT.pick_incoming_file_unit()
        if self.unit is None:
            return
  



    def make_revit_pt(self, x):
        if self.unit == 0:
                
            X = REVIT_UNIT.mm_to_internal(x[0])
            Y = REVIT_UNIT.mm_to_internal(x[1])
            Z = REVIT_UNIT.mm_to_internal(x[2])
            return DB.XYZ(X, Y, Z)
        elif self.unit == 1:
  
            return DB.XYZ(x[0], x[1], x[2])

    @ERROR_HANDLE.try_catch_error()
    def main(self, brep_data):

        #print brep_data
        self.vertex = []


        t = DB.Transaction(doc, 'Transfer Rhino srf to adp family.')

        t.Start()


        for i, pt_list in brep_data.items():
            pt_list = [self.make_revit_pt(x) for x in pt_list]
            try:
                self.add_adp_family(pt_list)
            except:
                print (traceback.format_exc())




        t.Commit()


        
        return



    def get_shared_ref_pt(self, pt):
        for ref_pt in self.vertex:

            if ref_pt.Position.IsAlmostEqualTo (pt, 0.001) :
                return ref_pt
        else:
            new_ref_pt = doc.FamilyCreate.NewReferencePoint(pt)
            self.vertex.append(new_ref_pt)

            return new_ref_pt

    def add_adp_family(self, pts):
  

        instance = DB.AdaptiveComponentInstanceUtils.CreateAdaptiveComponentInstance (doc, self.type)
        adp_pts = DB.AdaptiveComponentInstanceUtils.GetInstancePointElementRefIds (instance)
        #print adp_pts
        for i, adp_pt in enumerate(adp_pts):
            #print doc.GetElement(adp_pt)
            doc.GetElement(adp_pt).Position = pts[i]
            continue
            #print  doc.GetElement(adp_pt).Location.Position
         

            doc.GetElement(adp_pt).Location.Position = pts[i]#self.get_shared_ref_pt(pts[i])
        return instance
   
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    solution = Solution()
    T = DB.TransactionGroup(doc, __title__)
    T.Start()
    file = FOLDER.get_local_dump_folder_file("SRF2ADP_DATA")
    data = DATA_FILE.get_data(file)
    index = 1
    for brep_name, brep_data in data.items():
        
        print("processing: {} of {}".format(index, len(data)))
        index += 1

        
        solution.main(brep_data)
    SOUND.play_sound("sound_effect_mario_message.wav")
    T.Commit()
    
################## main code below #####################
output = script.get_output()
output.close_others()


if __name__ == "__main__":
    main()
   




