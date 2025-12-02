#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = "Export PDF, DWG, and JPG files organized by prefix and file type. Includes email notifications, time estimation, color/BW control, revision filtering, and sync options."
__title__ = "Ennead\nExporter"
__tip__ = True
__is_popular__ = True
import proDUCKtion # pyright: ignore 
proDUCKtion.validify()


from pyrevit import forms, script
from pyrevit.forms import WPFWindow
import shutil
import os
import sys
from pyrevit.revit import ErrorSwallower
import re
import time
from datetime import date
import math
import traceback

# this is needed only becasue when parsing tips from python files, a relative import will fail to find moudle
script_folder = os.path.dirname(__file__)
import sys
sys.path.append(script_folder)
import HELPER



from EnneadTab import JOKE, DATA_FILE, NOTIFICATION, SOUND, SPEAK, DOCUMENTATION
from EnneadTab import ERROR_HANDLE, FOLDER, IMAGE, LOG, USER
from EnneadTab.REVIT import REVIT_FORMS, REVIT_APPLICATION, REVIT_EVENT, REVIT_EXPORT, REVIT_SYNC
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import UI # pyright: ignore

DOC = REVIT_APPLICATION.get_doc()



from data_grid_id_map_obj import DataGridDocIdMapObj
from data_grid_preview_obj import DataGridPreviewObj
from email_data import EmailData




class SuperExporter(REVIT_FORMS.EnneadTabModelessForm):
    @ERROR_HANDLE.try_catch_error()
    def __init__(self):
        xamlfile = script.get_bundle_file('SuperExporter_UI.xaml')
        #print xamlfile
        WPFWindow.__init__(self, xamlfile)
        self.initiation_finished = False


        # important data setup
        self.setting_file = "super_exporter_setting"
        self.output_folder = "{}\\EnneadTab Exporter".format(FOLDER.DUMP_FOLDER)
        FOLDER.secure_folder(self.output_folder)


        self.export_queue = []
        self.selected_sheets = []

        self.load_setting()

        self.initiate_empty_data_grid_preview()
        #self.update_data_grid_map_id()
        self.bug_log = "Debug Output:"
        #self.update_debug("self.export_queue = ".format(self.export_queue))
        self.is_printing = False
        self.orginal_doc_name = DataGridDocIdMapObj.get_central_doc_name(DOC)

        # generic form setup
        self.folder_status_display.Content = ""





        self.progress_bar.Value = 0
        self.progress_bar_display.Text = "\n\n\n"

        self.button_main.Content = "Setting Incomplete"
        logo_file = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        self.set_image_source(self.logo_img, logo_file)
        self.set_image_source(self.update_icon, "update_icon.png")
        self.set_image_source(self.monitor_icon, "monitor_icon.png")





        self.initiate_para_list_source()
        self.initiate_dwg_setting_list_source()

        self.textbox_combined_pdf_name.Text = "{}_{}_Combined".format(date.today(), DOC.Title)
        
        # Initialize preview image system
        self._preview_file_toggle = True  # Start with previewA



        output = script.get_output()
        output.close_others()
        self.initiation_finished = True
        self.check_all_setting_ready()
        self.update_UI_enable_status()

    def print_debug(self, string):


        #print self.bug_log
        self.debug_panel.Text = string


    def update_debug(self, line):
        self.bug_log += "\n{}".format(line)




# index_all_sheets(get_full_docs(), print_out = False)
    def print_all_sheet_index(self):
        print ("--------indexing all the sheets including file not printing now.--------")
        sorted_dict = sorted(self.index_dict.items(), key = lambda x: x[1])
        #print sorted_dict
        for key, value in sorted_dict:
            print ("[{}] ---> {}".format(key, value))
        print ("-------- end of index--------")


    def index_all_sheets(self, print_out = False):

        def lookup_value(sheet, para_name):
            para = sheet.LookupParameter(para_name)
            if para:
                if para_name == "Sheet_$Order":
                    return para.AsInteger()
                else:
                    return para.AsString()
            else:
                return None
            
        self.index_dict = dict()
        for doc in self.docs_to_process:
            doc_sheets =  self.get_sheets_from_doc(doc)
            if doc_sheets == []:
                NOTIFICATION.messenger("Cannot find any good sheets in {}.\nCheck your Issue parameter name used to find sheets.".format(doc.Title))
                continue

            if self.radio_button_sheetGroup_sheetSeries_sheetNum_sheetName.IsChecked:

                doc_sheets.sort(key = lambda x: (lookup_value(x,"Sheet_$Group"),
                                                    lookup_value(x,"Sheet_$Series"),
                                                    x.SheetNumber),
                                                    reverse = False)
            else:
                if doc_sheets[0].LookupParameter("Sheet_$Order"):
                    doc_sheets.sort(key = lambda x: (lookup_value(x,"Sheet_$Order"),
                                                x.SheetNumber), reverse = False)
                else:
                    doc_sheets.sort(key = lambda x: x.SheetNumber, reverse = False)


            for i, sheet in enumerate(doc_sheets):
                self.index_dict[sheet.UniqueId] = "{0:03}".format( i + 1)


        if print_out:
            self.print_all_sheet_index()





    def get_availiable_issue_paras(self):
        sample_sheet = DB.FilteredElementCollector(DOC).OfClass(DB.ViewSheet).WhereElementIsNotElementType().FirstElement()
        if sample_sheet is None:
            out = ["No Issue Para Found."]
            return out
        out = []
        pattern = re.compile("Issue (.+)")
        pattern_additional = re.compile("Sheet_\$Issue(.+)")
        for para in sample_sheet.Parameters:
            """
            if "Issue" not in para.Definition.Name:
                continue
            """

            if  pattern.match(para.Definition.Name):
                out.append(para.Definition.Name)
                continue

            if  pattern_additional.match(para.Definition.Name):
                out.append(para.Definition.Name)
                continue

        out.sort()

        if len(out) == 0:
            out = ["No Issue Para Found."]
        return out




    def get_availiable_dwg_settings(self):
        existing_dwg_settings = DB.FilteredElementCollector(DOC).OfClass(DB.ExportDWGSettings).WhereElementIsNotElementType().ToElements()

        return [x.Name for x in existing_dwg_settings]

    def get_sheets_from_doc(self, doc):
        if doc is None:
            return []
        sheets = DB.FilteredElementCollector(doc).OfCategory(DB.BuiltInCategory.OST_Sheets).WhereElementIsNotElementType().ToElements()

        sheets = sorted(list(sheets), key = lambda x: x.SheetNumber)
        return filter(self.is_sheet_in_current_issue_para, sheets)



    def save_setting(self):

        current_setting_data = DATA_FILE.get_data(self.setting_file)



        out_data = dict()
        out_data["last_use_time"] = time.time()

        # get infor from doc name id pair to be used in step 1 grid table
        if current_setting_data.has_key("doc_names_id_pair"):
            temp = current_setting_data["doc_names_id_pair"]
        else:
            temp = dict()
        for item in self.data_grid_doc_id_map.ItemsSource:
            doc_name, id = item.doc_name, item.map_id
            temp[doc_name] = id
        out_data["doc_names_id_pair"] = temp


        # restore checkbox status for other
        out_data["is_export_dwg"] = self.checkbox_dwg.IsChecked
        out_data["is_export_pdf"] = self.checkbox_pdf.IsChecked
        out_data["is_export_jpg"] = self.checkbox_jpg.IsChecked
        out_data["is_name_format_with_plotId"] = self.radio_button_plotId_sheetNum_sheetName.IsChecked
        out_data["is_name_format_with_sheetGroup"] = self.radio_button_sheetGroup_sheetSeries_sheetNum_sheetName.IsChecked
        out_data["is_play_sound"] = self.checkbox_play_sound.IsChecked
        out_data["is_combine_pdf"] = self.checkbox_combine_pdf.IsChecked
        out_data["is_sync_and_close"] = self.checkbox_sync_and_close.IsChecked
        out_data["is_export_view_on_sheet"] = self.checkbox_dwg_view_export.IsChecked
        out_data["is_color_by_sheet"] = self.radio_button_color_by_sheet.IsChecked
        out_data["copy_folder_path"] = self.textbox_folder.Text
        out_data["is_copy_folder"] = self.checkbox_copy_folder.IsChecked
        out_data["is_send_email"] = self.checkbox_send_email.IsChecked
        out_data["is_delayed_start"] = self.checkbox_delayed_start.IsChecked
        if hasattr(self, 'scheduled_start_time'):
            # Handle both datetime objects and string values
            if hasattr(self.scheduled_start_time, 'isoformat'):
                out_data["scheduled_start_time"] = self.scheduled_start_time.isoformat()
            else:
                out_data["scheduled_start_time"] = self.scheduled_start_time


        out_data["issue_name"] = self.issue_name
        out_data["local_issue_para_name"] = self.textbox_local_isse_para_name.Text
        out_data["dwg_setting_name"] = self.dwg_setting_name


        self.email_data.update_info(self)
        out_data["email_data_receivers"] = self.email_data.receiver_list
        out_data["email_data_subject_line"] = self.email_data.subject
        out_data["email_data_body"] = self.email_data.body
        out_data["email_data_is_add_folder_link"] = self.email_data.is_adding_final_folder_link
        out_data["email_data_additional_attachments_list"] = self.email_data.additional_attachments_list
        out_data["email_data_embeded_images_list"] = self.email_data.embeded_images_list



        DATA_FILE.set_data(out_data, self.setting_file)

    def initiate_default_email_data(self):
        self.email_data = EmailData(receiver_list = self.email_receivers.Text,
                                    subject = self.email_subject_line.Text,
                                    body = self.email_body.Text,
                                    is_adding_final_folder_link = self.checkbox_add_folder_link.IsChecked)

    @ERROR_HANDLE.try_catch_error()
    def load_setting(self):
        try:
            data = DATA_FILE.get_data(self.setting_file)
        except:
        
            data = dict()
            DATA_FILE.set_data(data, self.setting_file)



        # set some default value if there were no json file before
        if not data:
            self.docs_to_process = [DOC]
            self.doc_names_id_pair = {DataGridDocIdMapObj.get_central_doc_name(DOC): "Ennead"}
            if DOC.IsWorkshared :
                self.doc_model_path_pair = {DataGridDocIdMapObj.get_central_doc_name(DOC): get_doc_path(DOC)}
            else:
                self.doc_model_path_pair = {DataGridDocIdMapObj.get_central_doc_name(DOC): None}
                NOTIFICATION.messenger(main_text = "This document is not workshared.")
            self.update_data_grid_map_id()
            self.is_export_dwg = self.checkbox_dwg.IsChecked
            self.is_export_pdf = self.checkbox_pdf.IsChecked
            self.is_export_jpg = self.checkbox_jpg.IsChecked
            self.is_name_format_with_plotId = self.radio_button_plotId_sheetNum_sheetName.IsChecked
            self.is_name_format_with_sheetGroup = self.radio_button_sheetGroup_sheetSeries_sheetNum_sheetName.IsChecked
            self.is_play_sound = self.checkbox_play_sound.IsChecked
            self.is_combine_pdf = self.checkbox_combine_pdf.IsChecked
            self.is_sync_and_close = self.checkbox_sync_and_close.IsChecked
            self.is_export_view_on_sheet = self.checkbox_dwg_view_export.IsChecked
            self.is_color_by_sheet = self.radio_button_color_by_sheet.IsChecked
            self.copy_folder_path = self.textbox_folder.Text
            self.is_copy_folder = self.checkbox_copy_folder.IsChecked
            self.is_delayed_start = self.checkbox_delayed_start.IsChecked

            self.initiate_para_list_source()
            self.initiate_dwg_setting_list_source()
            self.issue_name = self.issue_para_list.ItemsSource[self.issue_para_list.SelectedIndex]
            self.dwg_setting_name = self.dwg_setting_list.ItemsSource[self.dwg_setting_list.SelectedIndex]


            self.initiate_default_email_data()
            return False


        # retrive as much key as possible in class data
        for key, value in data.items():

            #print key
            #print value
            #getattr(self, key) ----> to read  data
            setattr(self, key, value)


        # restore previous form condition
        self.docs_to_process = [DOC]
        if DOC.IsWorkshared :
            self.doc_model_path_pair = {DataGridDocIdMapObj.get_central_doc_name(DOC): get_doc_path(DOC)}
        else:
            self.doc_model_path_pair = {DataGridDocIdMapObj.get_central_doc_name(DOC): None}
            NOTIFICATION.messenger(main_text = "This document is not workshared.")
        self.update_data_grid_map_id()
        self.checkbox_dwg.IsChecked = self.is_export_dwg
        self.checkbox_pdf.IsChecked = self.is_export_pdf
        self.checkbox_jpg.IsChecked = self.is_export_jpg
        self.radio_button_plotId_sheetNum_sheetName.IsChecked = self.is_name_format_with_plotId
        self.radio_button_sheetNum_sheetName.IsChecked = not(self.is_name_format_with_plotId)
        try:
            self.is_name_format_with_sheetGroup
        except:
            self.is_name_format_with_sheetGroup = False
        self.radio_button_sheetGroup_sheetSeries_sheetNum_sheetName.IsChecked = self.is_name_format_with_sheetGroup
        self.checkbox_play_sound.IsChecked = self.is_play_sound
        self.checkbox_combine_pdf.IsChecked = self.is_combine_pdf
        self.checkbox_sync_and_close.IsChecked = self.is_sync_and_close
        self.checkbox_dwg_view_export.IsChecked = self.is_export_view_on_sheet
        self.radio_button_color_by_sheet.IsChecked = self.is_color_by_sheet
        self.radio_button_color_BW_globally.IsChecked =not( self.is_color_by_sheet)
        self.textbox_folder.Text = self.copy_folder_path
        self.checkbox_copy_folder.IsChecked = self.is_copy_folder
        
        try:
            self.is_delayed_start
        except:
            self.is_delayed_start = False
        self.checkbox_delayed_start.IsChecked = self.is_delayed_start
        
        # Load scheduled start time if it exists
        try:
            if hasattr(self, 'scheduled_start_time') and self.scheduled_start_time:
                from datetime import datetime
                # IronPython 2.7 compatible datetime parsing
                try:
                    # Try to parse ISO format string manually
                    import re
                    # Convert to string if it's already a datetime object
                    time_str = str(self.scheduled_start_time)
                    # Match format like "2023-12-25T14:30:00" or "2023-12-25T14:30:00.123456"
                    match = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?', time_str)
                    if match:
                        year, month, day, hour, minute, second, microsecond = match.groups()
                        if microsecond:
                            # Pad microsecond to 6 digits
                            microsecond = microsecond.ljust(6, '0')[:6]
                            microsecond = int(microsecond)
                        else:
                            microsecond = 0
                        scheduled_time = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), microsecond)
                    else:
                        # Fallback: try to parse as simple date
                        scheduled_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                except:
                    # If all parsing fails, use current time
                    scheduled_time = datetime.now()
                now = datetime.now()
                
                # Calculate wait time
                wait_seconds = (scheduled_time - now).total_seconds()
                wait_minutes = int(wait_seconds // 60)
                wait_hours = int(wait_minutes // 60)
                remaining_minutes = wait_minutes % 60
                
                # Display the scheduled time
                if wait_hours > 0:
                    wait_display = "{}h {}m".format(wait_hours, remaining_minutes)
                else:
                    wait_display = "{}m".format(remaining_minutes)
                
                self.delayed_start_time_display.Text = "Scheduled: {}:{} (in {})".format(
                    str(scheduled_time.hour).zfill(2),
                    str(scheduled_time.minute).zfill(2),
                    wait_display
                )
        except:
            pass

        try:
            self.email_data = EmailData(receiver_list = self.email_data_receivers,
                                        subject = self.email_data_subject_line,
                                        body = self.email_data_body,
                                        is_adding_final_folder_link = self.email_data_is_add_folder_link,
                                        embeded_images_list = self.email_data_embeded_images_list,
                                        additional_attachments_list = self.email_data_additional_attachments_list)

            self.email_receivers.Text = self.email_data_receivers
            self.email_subject_line.Text = self.email_data_subject_line
            self.email_body.Text = self.email_data_body
            self.checkbox_add_folder_link.IsChecked = self.email_data_is_add_folder_link
            self.checkbox_send_email.IsChecked = self.is_send_email

        except Exception as e:
            print (e.message)
            self.initiate_default_email_data()


        """be careful when  to recover from json record, becasue if user switch to new doc,
            there might be no matching name.
        """
        for i, para in enumerate(self.get_availiable_issue_paras()):
            if self.issue_name  == para:
                self.issue_para_list.SelectedIndex = i + 1# to skip the default text on index 0
                break
        else:
            self.issue_para_list.SelectedIndex = 0

        try:
            self.textbox_local_isse_para_name.Text = self.local_issue_para_name
            if self.local_issue_para_name == self.issue_name:
                self.issue_name = self.textbox_local_isse_para_name.Text
        except:
            print (traceback.format_exc())
            pass # this for newly added check

        for i, setting in enumerate(self.get_availiable_dwg_settings()):
            if self.dwg_setting_name == setting:
                self.dwg_setting_list.SelectedIndex = i + 1# to skip the default text on index 0
                break
        else:
            self.dwg_setting_list.SelectedIndex = 0




        #except Exception as e:
            #print "Trouble reading data file becasue: {}".format(e)

        return True

    def initiate_para_list_source(self):
        para_list = self.get_availiable_issue_paras()
        para_list.insert(0,"...Pick Issue Para...")
        para_list.append("...Use Local Para Below...")
        self.issue_para_list.ItemsSource = para_list

    def initiate_dwg_setting_list_source(self):
        para_list = self.get_availiable_dwg_settings()
        para_list.insert(0,"...Pick DWG setting...")
        self.dwg_setting_list.ItemsSource = para_list



    def get_id_by_doc(self, doc):
        true_doc_name = DataGridDocIdMapObj.get_central_doc_name(doc)
        if not self.doc_names_id_pair.has_key(true_doc_name):
            self.doc_names_id_pair[true_doc_name] = "0"

        return self.doc_names_id_pair[true_doc_name]

    @property
    def issue_symbol(self):
        return u"\u25A0"

    def is_sheet_in_current_issue_para(self, sheet):

        if "internal" in self.issue_name.lower() and not sheet.LookupParameter(self.issue_name)  and sheet.LookupParameter(self.issue_name).AsString() == self.issue_symbol:
            return True


        if not sheet.LookupParameter("Appears In Sheet List").AsInteger():
            return False


        if not sheet.LookupParameter(self.issue_name):
            return False


        if sheet.LookupParameter(self.issue_name).AsString() is None:
            return False

        #print sheet.LookupParameter(self.issue_name).AsString()
        if len(sheet.LookupParameter(self.issue_name).AsString()) != 0:
            return True

        #### below not important anymore ########

        if sheet.LookupParameter(self.issue_name).AsString() !=  self.issue_symbol:
            return False

        return True


    def update_data_grid_map_id(self):
        self.docs_to_process.sort(key = lambda x:x.Title)
        self.data_grid_doc_id_map.ItemsSource = [DataGridDocIdMapObj(doc, self.get_id_by_doc(doc)) for  doc in self.docs_to_process]

    def initiate_empty_data_grid_preview(self):
        self.data_grid_preview.ItemsSource = []
        time_estimate = 0
        index = 999
        file_id = "-999"
        view_or_sheet = None
        extension = None
        is_in_height_light_zone = False
        for x in range(30):
            self.data_grid_preview.ItemsSource.append(DataGridPreviewObj(view_or_sheet, file_id, index, extension, time_estimate, is_in_height_light_zone))
        self.data_grid_preview_title.Text = "Pending valid setting..."



    def update_data_grid_preview(self):
        #print "!!!!about to update preview grid"
        self.export_queue = []# to hold all the sheet objs.
        self.record = dict()# hold time data
        for id_map_obj in self.data_grid_doc_id_map.ItemsSource:
            doc = id_map_obj.doc
            sheets = self.get_sheets_from_doc(doc)
            self.export_queue.extend(sheets)

            for key, value in self.get_time_estimate_from_record(doc).items():
                self.record[key] = value

        if len(self.selected_sheets) != 0:
            sheet_ids = [x.UniqueId for x in self.selected_sheets]
            self.export_queue = filter(lambda x: x.UniqueId in sheet_ids, self.export_queue)

        #print "before updating preview grid, the export queue is \n{}".format(self.export_queue)
        #self.update_debug("before updating preview grid, the export queue is {}".format(self.export_queue))
        self.data_grid_preview.ItemsSource = []
        self.index_all_sheets()
        is_in_height_light_zone = False
        self.export_queue.sort(key = lambda x: "{}_{}".format(self.get_id_by_doc(x.Document), self.index_dict[x.UniqueId]))

        def get_time_estimate_by_sheet_and_extension(sheet, extension):
            key = "{}#{}".format(sheet.UniqueId, extension)
            if key in self.record.keys():
                return self.record[key]
            return 0

        estimated_total = 0
        for sheet in self.export_queue:


            index = self.index_dict[sheet.UniqueId]
            if self.is_name_format_with_plotId:
                file_id = self.get_id_by_doc(sheet.Document)
            else:
                file_id = None

            if self.is_export_pdf:
                extension = ".pdf"
                time_estimate = get_time_estimate_by_sheet_and_extension(sheet, extension)
                estimated_total += time_estimate
                preview_obj = DataGridPreviewObj(sheet, file_id, index, extension, time_estimate, is_in_height_light_zone, is_sheet_group_prefix=self.is_name_format_with_sheetGroup)
                self.data_grid_preview.ItemsSource.append(preview_obj)

            if self.is_export_dwg:
                extension = ".dwg"
                time_estimate = get_time_estimate_by_sheet_and_extension(sheet, extension)
                estimated_total += time_estimate
                preview_obj = DataGridPreviewObj(sheet, file_id, index, extension, time_estimate, is_in_height_light_zone, is_sheet_group_prefix=self.is_name_format_with_sheetGroup)
                self.data_grid_preview.ItemsSource.append(preview_obj)

            if self.is_export_jpg:
                extension = ".jpg"
                time_estimate = get_time_estimate_by_sheet_and_extension(sheet, extension)
                estimated_total += time_estimate
                preview_obj = DataGridPreviewObj(sheet, file_id, index, extension, time_estimate, is_in_height_light_zone, is_sheet_group_prefix=self.is_name_format_with_sheetGroup)
                self.data_grid_preview.ItemsSource.append(preview_obj)

            # to flip height light color for next zone
            is_in_height_light_zone = not(is_in_height_light_zone)



        #self.data_grid_preview.ItemsSource.sort(key = lambda x: x.format_name)

        estimated_total = "{:.2f} mins".format(estimated_total / 60.0)
        self.data_grid_preview_title.Text = "{} items queued.\nEstimated total time = {}+. Total time excluding N/A item. ".format(len(self.data_grid_preview.ItemsSource), estimated_total)

        if len(self.data_grid_preview.ItemsSource) == 0:
            self.initiate_empty_data_grid_preview()
            self.button_main.IsEnabled = False
            self.button_main.Content = "Nothing to export.."




    def check_all_setting_ready(self):
        #self.print_debug()
        if not self.initiation_finished:
            return False

        self.button_main.BorderBrush = self.sample_color_disabled.Foreground


        if self.is_export_dwg + self.is_export_jpg + self.is_export_pdf == 0:
            self.button_main.Content = "Need at least one extension."
            self.initiate_empty_data_grid_preview()
            return False


        if self.is_copy_folder and self.copy_folder_path == "Folder Path...":
            self.button_main.Content = "Copy folder path missing."
            return False


        if self.issue_name == self.issue_para_list.ItemsSource[0]:
            self.button_main.Content = "Issue parameter not picked."
            self.initiate_empty_data_grid_preview() #this will affect what should display, so should update
            return False


        if self.issue_name == self.issue_para_list.ItemsSource[-1]:
            self.issue_name = self.textbox_local_isse_para_name.Text
            if len(self.issue_name) == 0:
                self.button_main.Content = "Locally defined issue Parameter cannot be empty."
                return False


        if self.is_export_dwg and self.dwg_setting_name == self.dwg_setting_list.ItemsSource[0]:
            self.button_main.Content = "DWG setting not picked."
            return False

        # check setting A, return False if not pass


        # cehck setting B, return False if not pass
        
        for item in self.data_grid_preview.ItemsSource:
            if "*" in item.format_name:
                NOTIFICATION.messenger("Please remove * at " + item.format_name)
                self.button_main.Content = "There are * in some name."
                return False




        # after passing all test, the script is readt to action export
        self.button_main.IsEnabled = True
        self.button_main.Content = "Ready to export!"
        self.button_main.BorderBrush = self.sample_color_green.Foreground

        self.update_data_grid_map_id() #this step is needed during iniitalization process
        self.update_data_grid_preview()
        return True
            #self.button_rename.Foreground = "#FF464646"






    def active_original_doc(self, doc_name):
        print ("!!!!!!!Activate {} ".format(doc_name))
        model_path = self.doc_model_path_pair[doc_name]




        # this model path  is server path
        open_options = DB.OpenOptions()
        #ERROR_HANDLE.print_note( "setting active doc as {}".format(data[0]))
        try:
            return UI.UIApplication(REVIT_APPLICATION.get_app()).OpenAndActivateDocument (model_path,
                                                                                            open_options,
                                                                                            False)
        except Exception as e:
            print (traceback.format_exc())
            return None

    def open_doc_in_background(self, doc_name):
        #print "!!!Opening {} in background".format(doc_name)
        model_path = self.doc_model_path_pair[doc_name]
        open_options = DB.OpenOptions()
        if isinstance(model_path, DB.ModelPath):
            new_doc = REVIT_APPLICATION.get_app().OpenDocumentFile(model_path,
                                                                    open_options)
        elif isinstance(model_path, str):
            new_doc = REVIT_APPLICATION.get_app().OpenDocumentFile(model_path)

        #output.print_md( "background open file {}".format(doc_name))


    @ERROR_HANDLE.try_catch_error()
    def main_export_Clicked(self, sender, args):###sender and args must be here even when not used to pass data between GUI and python

        if "export finish" in self.button_main.Content.lower():
            self.Close()
            return

        if not self.check_all_setting_ready():
            return

        # ---- pre action ----
        self.save_setting()
        
        # Handle delayed start if enabled
        if self.is_delayed_start and hasattr(self, 'scheduled_start_time'):
            self._execute_delayed_start(self.scheduled_start_time)
        
        self.monitor_group.Visibility, self.data_grid_preview.Visibility = self.data_grid_preview.Visibility,self.monitor_group.Visibility




        self.doc_names_already_open = [DataGridDocIdMapObj.get_central_doc_name(x) for x in REVIT_APPLICATION.get_top_revit_docs()]
        self.docs_to_be_opened_by_API = [x for x in self.docs_to_process if DataGridDocIdMapObj.get_central_doc_name(x) not in self.doc_names_already_open]

        #depress open hook
        REVIT_EVENT.set_open_hook_depressed(stage = True)
        # ARCHI_UTILITY.set_doc_change_hook_depressed(stage = True)
        # ERROR_HANDLE.print_note("my doc change hook depress satus = {}".format(ARCHI_UTILITY.is_doc_change_hook_depressed()))

        time_start = time.time()
        #open background doc that neeed to be opeend
        with ErrorSwallower() as swallower:
            for doc in self.docs_to_be_opened_by_API:
                #print doc.Title
                self.open_doc_in_background(doc.Title)
        #timer how long background files used to open
        time_end = time.time()

        if len(self.docs_to_be_opened_by_API) > 0:
            REVIT_EXPORT.print_time("background loading {} files".format(self.docs_to_be_opened_by_API), time_end, time_start, use_minutes = False)

            ###!!!! no need to reactive primary doc if we are using post file name correction method
            #primary_doc = active_original_doc(orginal_doc_name).Document##function return UI doc ##try this to fix main doc pdf not print issue



        #open hook depression re-enable
        REVIT_EVENT.set_open_hook_depressed(stage = False)









        # ---- ACTION BEGIN ----

        self.Topmost = True
        self.is_printing = True
        self.is_printing_interupted = False
        self.button_cancel_export.Visibility = self.button_main.Visibility
        self.button_main.Content = "Exporting..."
        self.files_exported_for_this_issue = []


        #this is done here primaryly for the dwg bundles. The inner views need to know the file id as it comes out.
        self.file_id_dict = dict()
        for item in self.data_grid_preview.ItemsSource:
            self.file_id_dict[item.format_name] = item.file_id

        self.progress_bar.Value = 0
        self.progress_bar.Maximum = len(self.data_grid_preview.ItemsSource)
        #self.progress_bar.Visible  = True


        job_time_start = time.time()
        print("Let The Printing Begin:")
        self.Topmost = False
        current_sheet_id = None
        for i, preview_obj in enumerate(self.data_grid_preview.ItemsSource):
            if not self.is_printing:
                break
            #print "simulate print-->" + str(preview_obj)

            print ("\n\n-------{}/{} preparing : {} ---------".format(i + 1, len(self.data_grid_preview.ItemsSource), preview_obj))
            if len(self.data_grid_preview.ItemsSource) - i < 5:
                SPEAK.speak(None)

            time_start = time.time()
            # main export action
            #self.export(item)
            #print dir(preview_obj)
            view_or_sheet = preview_obj.item
            extension = preview_obj.extension
            file_name = preview_obj.format_name
            raw_name = preview_obj.raw_name

            # only update preview image for new sheet
            if current_sheet_id != view_or_sheet.UniqueId:
                self.update_preview_image(view_or_sheet)
                current_sheet_id = view_or_sheet.UniqueId

            #update laoding status for every export item
            self.update_loading_message(preview_obj)



            # file_name here contains extension; delete safely in case file is moved/absent. Or maybe this was a folder for the packaged dwg with parts
            try:
                target_path = os.path.join(self.output_folder, file_name)
                if os.path.exists(target_path):
                    if os.path.isfile(target_path):
                        os.remove(target_path)
                    if os.path.isdir(target_path):
                        shutil.rmtree(target_path)  
            except OSError as e:
                import errno
                # Ignore if file is already gone; rethrow other errors
                if not (hasattr(e, 'errno') and e.errno == errno.ENOENT):
                    raise


            if extension == ".pdf":
                is_color_by_sheet = self.is_color_by_sheet
                final_file = REVIT_EXPORT.export_pdf(view_or_sheet, raw_name, self.output_folder, is_color_by_sheet)
                # Only append if export was successful (not None)
                if final_file is not None:
                    self.files_exported_for_this_issue.append(final_file)
                else:
                    print("Export skipped for: {} - non-exportable views detected".format(preview_obj.format_name))

            if extension == ".dwg":
                is_export_view_on_sheet = self.is_export_view_on_sheet
                dwg_setting_name = self.dwg_setting_name
                DWG_option = DB.DWGExportOptions().GetPredefinedOptions(view_or_sheet.Document, dwg_setting_name)
                if DWG_option:
                    if is_export_view_on_sheet:
                        local_output_folder = os.path.join(self.output_folder, file_name)
                        if not os.path.exists(local_output_folder):
                            os.makedirs(local_output_folder)
                    else:
                        local_output_folder = self.output_folder
                    final_files = REVIT_EXPORT.export_dwg(view_or_sheet, raw_name, local_output_folder, dwg_setting_name, is_export_view_on_sheet)

                    self.files_exported_for_this_issue.extend(final_files)
                    for new_files in final_files:
                        self.file_id_dict[new_files] = self.file_id_dict[preview_obj.format_name]
                else:
                    print ("###############Cannot find this setting in the doc...cancel exporting...")
                    final_files = []
                    #is_success = False

            if extension == ".jpg":
                final_file = REVIT_EXPORT.export_image(view_or_sheet, raw_name, self.output_folder,  is_color_by_sheet = self.is_color_by_sheet)
                self.files_exported_for_this_issue.append(final_file)

            time_end = time.time()
            format_time = REVIT_EXPORT.print_time("sheet to {}".format(extension), time_end, time_start)
            preview_obj.time_estimate = time_end - time_start


            """copy new created file to final folder now"""
            remaining_objs = self.data_grid_preview.ItemsSource[i:]
            remaining_time = 0
            for obj in remaining_objs:
                remaining_time += obj.time_estimate
            remaining_time_min_part = int(math.floor(remaining_time / 60))
            remaining_time_sec_part = int(remaining_time % 60)
            remaining_time = "{:.2f} mins = {}m {}s".format(remaining_time / 60.0, remaining_time_min_part, remaining_time_sec_part)
            self.progress_bar.Value = i + 1
            self.progress_bar_display.Text = "{}/{}\nProcessing {}\n{}".format(int(self.progress_bar.Value),\
                                                                int(self.progress_bar.Maximum), \
                                                                file_name,
                                                                "Estimated remaining time, exluding N/A items = {}".format(remaining_time))


            if self.is_copy_folder:
                if extension == ".dwg":
                    new_contents = final_files
                else:
                    new_contents = [final_file]
                REVIT_EXPORT.dump_exported_files_to_copy_folder(self.output_folder, new_contents, self.file_id_dict, self.copy_folder_path)


            # ----- end of for loop


        # ----- after exporting ------
        self.monitor_group.Visibility, self.data_grid_preview.Visibility = self.data_grid_preview.Visibility,self.monitor_group.Visibility

        self.Topmost = False
        self.button_main.Width = 600
        self.button_main.Content = "Export Finish, Start Another Job By Reopening Exporter"
        print ("Following are the files exported this time:")
        for file in self.files_exported_for_this_issue:
            print (file)
        print ("--exported files ends")



        self.is_printing = False
        self.button_cancel_export.Visibility = self.sample_color_enabled.Visibility
        self.initiate_loading_message()
        self.update_time_estimate()




        copy_folder = self.copy_folder_path if self.is_copy_folder else None

        if self.is_export_jpg:
            primary_doc = self.active_original_doc(self.orginal_doc_name) #!!!when exporting image, the exportimage method will force activate the doc. So we need to switch back primary doc so other can be closed.(tested in 2022 and before)


        #close daocs opeeedn by API
        REVIT_APPLICATION.close_docs_by_name(names = [x.Title for x in self.docs_to_be_opened_by_API], close_all = False)




        # ARCHI_UTILITY.set_doc_change_hook_depressed(stage = False)
        # ERROR_HANDLE.print_note("my doc change hook depress status = {}".format(ARCHI_UTILITY.is_doc_change_hook_depressed()))

        if self.is_copy_folder:

            REVIT_EXPORT.dump_exported_files_to_copy_folder(self.output_folder, self.files_exported_for_this_issue, self.file_id_dict, copy_folder)

        if self.is_combine_pdf and not self.is_printing_interupted:
            combined_pdf_name = self.textbox_combined_pdf_name.Text
            REVIT_EXPORT.combine_final_pdf(self.output_folder, self.files_exported_for_this_issue, combined_pdf_name, copy_folder)

        if self.is_play_sound:
            SOUND.play_sound("sound_effect_mario_stage_clear.wav")




        job_time_end = time.time()
        total_time_second = int(job_time_end - job_time_start)
        total_time_min = int( total_time_second / 60 )
        print ("#"*20)
        print ("all sheets from selected revit files have been printed.\nIssue parameter = [{}]".format(self.issue_name))
        REVIT_EXPORT.print_time("Print {} sheets".format(len(self.files_exported_for_this_issue)), time_end, time_start, use_minutes = True)
        print ("#"*20)
        self.print_ranked_log()
        # ERROR_HANDLE.print_note("my doc change hook depress satus = {}".format(ARCHI_UTILITY.is_doc_change_hook_depressed()))
        ERROR_HANDLE.print_note("###END OF TOOL###")

        time_obj = time.localtime()
        localtime = "{}-{}-{}_{}-{}-{}".format(time_obj.tm_year,
                                    time_obj.tm_mon,
                                    time_obj.tm_mday,
                                    time_obj.tm_hour,
                                    time_obj.tm_min,
                                    time_obj.tm_sec)
        self.log_file = "EnneadTab Exporter AutoSave Log_{}.html".format(localtime)
        self.log_file_path = "{}\{}".format(self.output_folder , self.log_file)
        output.save_contents(self.log_file_path)






        print ("####")
        print (self.is_sync_and_close, self.is_printing_interupted)
        print ("####")
        if self.is_sync_and_close and not self.is_printing_interupted:
            REVIT_SYNC.sync_and_close()
            self.Close()

        total_time_min_part = int(math.floor(total_time_second / 60))
        total_time_sec_part = int(total_time_second % 60)

        REVIT_FORMS.notification(main_text = "EnneadTab Export done.",
                                        sub_text = "Total time = {}m {}s".format(total_time_min_part, total_time_sec_part),
                                        window_title = "EnneadTab Exporter",
                                        button_name = "Close",
                                        self_destruct = 0,
                                        window_height = 300)


        ending_announcement = "enni-ed tab exporter has just finished exporting {} items after {} minutes and {} seconds.".format(len(self.files_exported_for_this_issue), total_time_min_part, total_time_sec_part)
        if self.is_send_email:
            ending_announcement += "Also, an email is scheduled to sent. Subject line: {}".format(self.email_subject_line.Text.lower().replace("ennead", "enni-ed "))
        SPEAK.speak(ending_announcement)

        if not self.is_sync_and_close:
            self.update_data_grid_preview()


        if self.is_send_email:
            safety = 0
            while True:
                safety += 1
                if os.path.exists(self.log_file_path):
                    SPEAK.speak("Output log file saved.")
                    break

                if safety % 5 == 0:
                    SPEAK.speak("Waiting for output log file to save.")
                time.sleep(1)


                if safety > 50:
                    break
            self.email_data.update_info(self)
            self.email_data.send()
            SPEAK.speak("Email is scheduled to send.")

    def print_ranked_log(self):
        rank_list = self.data_grid_preview.ItemsSource[:]

        rank_list.sort(key = lambda x:x.time_estimate, reverse = True)
        output.print_md( "## Ranked export time below:")

        for item in rank_list:
            time = item.time_estimate
            export_item = item.format_name
            if time > 120:
                mins = int(time/60)
                output.print_md(":warning: < **{}** > use ***{}*** mins".format(export_item, mins))
            else:
                output.print_md("< **{}** > use ***{}*** seconds".format(export_item, time))



    def extension_options_changed(self, sender, args):
        #print "options_changed"
        self.is_export_dwg = self.checkbox_dwg.IsChecked
        self.is_export_pdf = self.checkbox_pdf.IsChecked
        self.is_export_jpg = self.checkbox_jpg.IsChecked
        #self.print_opt_status()
        self.update_UI_enable_status()
        self.check_all_setting_ready()

    def checkbox_additional_setting_changed(self, sender, args):
        self.is_export_view_on_sheet = self.checkbox_dwg_view_export.IsChecked
        self.is_copy_folder = self.checkbox_copy_folder.IsChecked
        self.is_play_sound = self.checkbox_play_sound.IsChecked
        self.is_combine_pdf = self.checkbox_combine_pdf.IsChecked
        self.is_sync_and_close = self.checkbox_sync_and_close.IsChecked
        self.is_send_email = self.checkbox_send_email.IsChecked
        self.is_delayed_start = self.checkbox_delayed_start.IsChecked

        # Handle delayed start checkbox change
        if sender == self.checkbox_delayed_start:
            if self.is_delayed_start:
                self.handle_delayed_start_time_selection()
            else:
                # Clear the display when unchecked
                self.delayed_start_time_display.Text = ""
                if hasattr(self, 'scheduled_start_time'):
                    delattr(self, 'scheduled_start_time')

        self.update_UI_enable_status()
        self.check_all_setting_ready()

    @ERROR_HANDLE.try_catch_error()
    def handle_delayed_start_time_selection(self):
        """Handle time selection when delayed start checkbox is checked."""
        from datetime import datetime, timedelta
        
        # Use text input method directly (Windows Forms is causing issues)
        self._handle_delayed_start_text_input_fallback()

    def _handle_delayed_start_text_input_fallback(self):
        """Fallback method using text input for time selection."""
        from datetime import datetime, timedelta
        
        while True:
            # Get time input from user
            # Calculate default time (current time + 5 minutes)
            now = datetime.now()
            default_time = now + timedelta(minutes=5)
            
            time_input = forms.ask_for_string(
                default='{}:{}'.format(
                    str(default_time.hour).zfill(2),
                    str(default_time.minute).zfill(2)
                ),
                prompt='Enter start time in HH:MM format (24-hour):\nExample: 14:30 for 2:30 PM'
            )
            
            if not time_input:
                # User cancelled, uncheck the checkbox
                self.checkbox_delayed_start.IsChecked = False
                self.is_delayed_start = False
                self.delayed_start_time_display.Text = ""
                return
            
            try:
                # Parse the input time
                hour, minute = map(int, time_input.split(':'))
                
                # Validate time format
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    forms.alert('Invalid time format. Please enter time in HH:MM format (24-hour).\nHour: 0-23, Minute: 0-59')
                    continue
                
                # Create target datetime for today
                now = datetime.now()
                target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If the time has already passed today, set it for tomorrow
                if target_time <= now:
                    target_time += timedelta(days=1)
                
                # Store the scheduled time
                self.scheduled_start_time = target_time
                
                # Calculate wait time
                wait_seconds = (target_time - now).total_seconds()
                wait_minutes = int(wait_seconds // 60)
                wait_hours = int(wait_minutes // 60)
                remaining_minutes = wait_minutes % 60
                
                # Display the scheduled time
                if wait_hours > 0:
                    wait_display = "{}h {}m".format(wait_hours, remaining_minutes)
                else:
                    wait_display = "{}m".format(remaining_minutes)
                
                self.delayed_start_time_display.Text = "Scheduled: {}:{} (in {})".format(
                    str(target_time.hour).zfill(2),
                    str(target_time.minute).zfill(2),
                    wait_display
                )
                
                NOTIFICATION.messenger("Export scheduled for {}:{} (in {})".format(
                    str(target_time.hour).zfill(2),
                    str(target_time.minute).zfill(2),
                    wait_display
                ))
                break
                    
            except ValueError:
                forms.alert('Invalid time format. Please enter time in HH:MM format.\nExample: 14:30 for 2:30 PM')
                continue
            except Exception as e:
                ERROR_HANDLE.print_note("Error in delayed start: {}".format(str(e)))
                forms.alert('Error setting delayed start. Please try again.')
                continue

    def update_UI_enable_status(self):
        disabled_color = self.sample_color_disabled.Foreground
        enabled_color = self.sample_color_enabled.Foreground


        # DWG related enable check
        self.checkbox_dwg_view_export.IsEnabled = self.is_export_dwg
        if self.is_export_dwg:
            self.checkbox_dwg_view_export.Foreground = enabled_color
        else:
            self.checkbox_dwg_view_export.Foreground = disabled_color


        # PDF related enable check
        self.checkbox_combine_pdf.IsEnabled = self.is_export_pdf
        self.radio_button_color_by_sheet.IsEnabled = self.is_export_pdf
        self.radio_button_color_BW_globally.IsEnabled = self.is_export_pdf
        if self.is_export_pdf:
            self.checkbox_combine_pdf.Foreground = enabled_color
            self.radio_button_color_by_sheet.Foreground = enabled_color
            self.radio_button_color_BW_globally.Foreground = enabled_color
        else:
            self.checkbox_combine_pdf.Foreground = disabled_color
            self.radio_button_color_by_sheet.Foreground = disabled_color
            self.radio_button_color_BW_globally.Foreground = disabled_color

        # combined pdf UI check
        self.textbox_combined_pdf_name.IsEnabled = self.checkbox_combine_pdf.IsEnabled
        if self.is_combine_pdf:
            self.textbox_combined_pdf_name.Foreground = enabled_color
        else:
            self.textbox_combined_pdf_name.Foreground = disabled_color

        if self.copy_folder_path != "Folder Path...":
            self.button_open_copy_folder.IsEnabled = True
        else:
            self.button_open_copy_folder.IsEnabled = False



        # Email related
        self.email_receivers.IsEnabled = self.checkbox_send_email.IsChecked
        self.email_subject_line.IsEnabled = self.checkbox_send_email.IsChecked
        self.email_body.IsEnabled = self.checkbox_send_email.IsChecked
        self.checkbox_add_folder_link.IsEnabled = self.checkbox_send_email.IsChecked


    @ERROR_HANDLE.try_catch_error()
    def local_issue_para_text_changed(self, sender, args):
        self.issue = self.textbox_local_isse_para_name.Text
        if len(self.issue_name) == 0:
            self.button_main.Content = "Locally defined issue Parameter cannot be empty."
        self.update_data_grid_preview()


    def name_format_changed(self, sender, args):
        self.is_name_format_with_plotId = self.radio_button_plotId_sheetNum_sheetName.IsChecked
        self.is_name_format_with_sheetGroup = self.radio_button_sheetGroup_sheetSeries_sheetNum_sheetName.IsChecked


        self.update_data_grid_preview()


    def color_setting_changed(self, sender, args):
        self.is_color_by_sheet = self.radio_button_color_by_sheet.IsChecked

    def button_pick_docs_Clicked(self, sender, args):
        if len([doc for doc in REVIT_APPLICATION.get_top_revit_docs() if not doc.IsFamilyDocument]) > 1:
            # too many top doc
            REVIT_FORMS.dialogue(main_text = "I notice you have other document opened right now in this session.",
                                sub_text = "In order to avoid version conflicting, EnneadTab Exporter try to export opened docs only, no export from link.\n\nTo export from links, close all other files and only leave one open.")
            docs = REVIT_APPLICATION.select_top_level_docs(select_multiple = True)


        else:
            # ok, only one top doc
            docs = REVIT_APPLICATION.select_revit_link_docs(select_multiple = True, including_current_doc = True)
        if not docs:
            docs = [DOC]
        self.docs_to_process = docs

        self.check_all_setting_ready()

        # update the model path pair
        self.doc_model_path_pair = dict()
        for item in self.data_grid_doc_id_map.ItemsSource:
            doc_name, id = item.doc_name, item.map_id
            self.doc_names_id_pair[doc_name] = str(id)
            self.doc_model_path_pair[doc_name] = get_doc_path(item.doc)

        #adding additional self doc data in case user are only print link, in that case we need a way to go back to original doc
        self.doc_model_path_pair[self.orginal_doc_name] = get_doc_path(DOC)

    def pick_copy_folder_Clicked(self, sender, args):
        title_line = 'Pick the folder ...'
        with forms.WarningBar(title = title_line):
            folder = None
            while folder is None:
                folder = forms.pick_folder(title = title_line)
        self.folder_status_display.Content = "Folder Picked!"
        self.set_image_source(self.status_icon, "ok_icon.png")
        self.textbox_folder.Text = folder
        self.copy_folder_path = folder

        self.check_all_setting_ready()


    def show_feature_Clicked(self, sender, args):
        notes_A = ["Export from linked Revit.",
                "Formated names.",
                "Multiple file extension.",
                "Export by issue.",
                "Change color setting per sheet.",
                "Isolated view export for dwg."]

        notes_B = ["Alert after finish.",
                "Upload to folder with subfolder.",
                "Sync and close after export.",
                "Ordering output.",
                "Record time estimate.",
                "Auto combine PDF."]
        self.feature_sum_note = ""
        for note in notes_A + notes_B:
            self.feature_sum_note += "\n -{}".format(note)


        REVIT_FORMS.notification(main_text = "Features:",
                                sub_text = self.feature_sum_note)

    def button_save_setting_Clicked(self, sender, args):

        self.save_setting()
        self.Close()


    def button_close_window_Clicked(self, sender, args):
        # Clean up preview images before closing
        self._cleanup_old_preview_images()
        self.Close()

    def selective_export_Clicked(self, sender, args):
        class MyOption(forms.TemplateListItem):
            @property
            def name(self):
                return "[{}] {} - {}".format(DataGridDocIdMapObj.get_central_doc_name(self.item.Document), self.item.SheetNumber, self.item.Name)

        temp = []
        for id_map_obj in self.data_grid_doc_id_map.ItemsSource:
            doc = id_map_obj.doc
            sheets = self.get_sheets_from_doc(doc)
            temp.extend(sheets)
        sheet_pool = [MyOption(x) for x in temp]
        sels = forms.SelectFromList.show(sheet_pool, name_attr = "Name", multiselect = True, title = "Select Desired Sheets")
        if sels and len(sels) < len(temp):
            self.selected_sheets = sels
            self.button_selective_export.Content = "Showing Selected Only"
        else:
            self.selected_sheets = []
            self.button_selective_export.Content = "Go Selective"
        self.update_data_grid_preview()


    def dropdown_issue_para_list_value_changed(self, sender, args):
        self.issue_name = self.issue_para_list.ItemsSource[self.issue_para_list.SelectedIndex]
        res = self.check_all_setting_ready()
        #print "after change issue dropdown, the check setting status is {}".format(res)
        #self.update_debug("after change issue dropdown, the check setting status is {}".format(res))


    def dropdown_dwg_setting_value_changed(self, sender, args):
        self.dwg_setting_name = self.dwg_setting_list.ItemsSource[self.dwg_setting_list.SelectedIndex]
        res = self.check_all_setting_ready()
        #print "after change dwg dropdown, the check setting status is {}".format(res)
        #self.update_debug("after change dwg dropdown, the check setting status is {}".format(res))

    def cancel_export_Clicked(self, sender, args):
        #print "cancel print..."
        self.button_cancel_export.Visibility = self.sample_color_enabled.Visibility
        self.is_printing = False
        self.is_printing_interupted = True

    def open_log_Clicked(self, sender, args):
        #print os.listdir(self.output_folder)
        logs = filter(lambda x:x.startswith("EnneadTab Exporter AutoSave Log"), os.listdir(self.output_folder))
        if len(logs) == 0:
            return

        logs.sort(reverse = True)
        sel = forms.SelectFromList.show(logs, multiple = False, title = "Pick a log")
        if not sel:
            return

        file = "{}\{}".format(self.output_folder, sel)
        os.startfile(file)


    def show_sample_marker_Clicked(self, sender, args):
        filepath = DOCUMENTATION.get_text_path_by_name("_emoji_text.txt")
        os.startfile(filepath)
        
        
    def generate_issue_Clicked(self, sender, args):
        if not hasattr(self, "docs_to_process"):
            self.docs_to_process = [doc]
            
        issue_name = forms.ask_for_string("Sheet_$Issue_XXXX")
        
        for doc in self.docs_to_process:
            if doc.IsLinked:
                NOTIFICATION.messenger('[{}] is a link file, cannot edit.'.format(doc.Title))
                continue
            HELPER.create_issue_para_to_sheet(doc, issue_name)
        
        
        self.initiate_para_list_source()



    def generate_print_in_color_Clicked(self, sender, args):
        if not hasattr(self, "docs_to_process"):
            self.docs_to_process = [doc]
            
        
        
        for doc in self.docs_to_process:
            if doc.IsLinked:
                NOTIFICATION.messenger('[{}] is a link file, cannot edit.'.format(doc.Title))
                continue
            HELPER.create_color_setting_to_sheet(doc)
        

        return
    




    def open_local_folder_Clicked(self, sender, args):
        path = os.path.realpath(self.output_folder)
        os.startfile(path)


    def open_copy_folder_Clicked(self, sender, args):
        path = os.path.realpath(self.copy_folder_path)
        os.startfile(path)

    def update_doc_id_pair_Changed(self, sender, args):


        self.print_debug("pair changed.")
        self.doc_model_path_pair = dict()
        #udpate the data in the pool
        for item in self.data_grid_doc_id_map.ItemsSource:
            doc_name, id = item.doc_name, item.map_id
            #print doc_name, id
            self.doc_names_id_pair[doc_name] = str(id)
            self.doc_model_path_pair[doc_name] = get_doc_path(item.doc)

        self.check_all_setting_ready()



    def update_preview_image(self, view_or_sheet):
        """Updates the preview image for a view or sheet using alternating preview files.
        
        Uses previewA and previewB to avoid file conflicts when WPF form is displaying images.
        
        Args:
            view_or_sheet: Revit ViewSheet or View object to preview
        """
        
        try:
            # Clean up old preview images first
            self._cleanup_old_preview_images()
            
            # Determine which preview file to use (alternate between A and B)
            if not hasattr(self, '_preview_file_toggle'):
                self._preview_file_toggle = True  # Start with A
            
            preview_filename_naked = "previewA" if self._preview_file_toggle else "previewB"
            
            # Try to export the preview image with retries
            real_preview_file_exported = None
            for attempt in range(3):
                try:
                    real_preview_file_exported = REVIT_EXPORT.export_image(
                                                                view_or_sheet,
                                                                preview_filename_naked,
                                                                FOLDER.DUMP_FOLDER,
                                                                is_thumbnail=True)
                    
                    if real_preview_file_exported:
                        break
                        
                    if attempt < 2:  # Don't sleep on the last attempt
                        import time
                        time.sleep(0.5)  # Small delay before retry
                except Exception as e:
                    ERROR_HANDLE.print_note("Preview export attempt {} failed: {}".format(attempt + 1, str(e)))
                    if attempt < 2:
                        import time
                        time.sleep(0.5)
            
            if not real_preview_file_exported:
                ERROR_HANDLE.print_note("Failed to export preview image for {} after 3 attempts".format(view_or_sheet.Name))
                return
                
            full_path = FOLDER.get_local_dump_folder_file(real_preview_file_exported)
            
            if not os.path.exists(full_path):
                ERROR_HANDLE.print_note("Preview image file not found: {}".format(full_path))
                return
            
            # Wait for file to be ready
            if not FOLDER.wait_until_file_is_ready(full_path):
                ERROR_HANDLE.print_note("Preview image file not ready: {}".format(full_path))
                return
                
            self.set_image_source(self.preview_image, full_path)
            
            # Toggle for next use
            self._preview_file_toggle = not self._preview_file_toggle
            
        except Exception as e:
            ERROR_HANDLE.print_note("Failed to update preview image for {}: {}".format(view_or_sheet.Name, str(e)))
            import traceback
            ERROR_HANDLE.print_note(traceback.format_exc())
    
    def _cleanup_old_preview_images(self):
        """Clean up old preview images to prevent file conflicts."""
        try:
            import time
            current_time = int(time.time())
            
            for filename in os.listdir(FOLDER.DUMP_FOLDER):
                # Only clean up preview files, not regular export files
                if (filename.startswith("previewA") or filename.startswith("previewB")) and filename.endswith(".jpg"):
                    file_path = os.path.join(FOLDER.DUMP_FOLDER, filename)
                    try:
                        # Check if file is older than 2 minutes to avoid deleting active files
                        if os.path.exists(file_path):
                            file_age = current_time - int(os.path.getmtime(file_path))
                            if file_age > 120:  # 2 minutes
                                os.remove(file_path)
                    except Exception as e:
                        # If removal fails, just skip it - don't try to rename
                        pass
        except Exception as e:
            ERROR_HANDLE.print_note("Preview cleanup error: {}".format(str(e)))
            pass  # If cleanup fails, continue anyway
      



    def initiate_loading_message(self):
        self.textblock_export_status.Text = "..."
        self.textblock_load_screen.Text = "..."

    def update_loading_message(self, preview_obj):
        self.textblock_export_status.Text = "{}\nEstimated time = {}".format( preview_obj.format_name, preview_obj.time_estimate_format)
        self.textblock_load_screen.Text = JOKE.random_loading_message()

    
    def _execute_delayed_start(self, target_time):
        """Execute the delayed start with the given target time."""
        from datetime import datetime
        
        # Convert target_time to datetime if it's a string
        if isinstance(target_time, str):
            # IronPython 2.7 compatible datetime parsing
            try:
                # Try to parse ISO format string manually
                import re
                # Match format like "2023-12-25T14:30:00" or "2023-12-25T14:30:00.123456"
                match = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?', target_time)
                if match:
                    year, month, day, hour, minute, second, microsecond = match.groups()
                    if microsecond:
                        # Pad microsecond to 6 digits
                        microsecond = microsecond.ljust(6, '0')[:6]
                        microsecond = int(microsecond)
                    else:
                        microsecond = 0
                    target_time = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), microsecond)
                else:
                    # Fallback: try to parse as simple date
                    target_time = datetime.strptime(target_time, '%Y-%m-%d %H:%M:%S')
            except:
                # If all parsing fails, use current time
                target_time = datetime.now()
        
        # Check if scheduled time has already passed
        now = datetime.now()
        if target_time <= now:
            # Scheduled time has passed, start immediately
            NOTIFICATION.messenger("Scheduled time has already passed. Starting export immediately...")
            self.button_main.Content = "Starting export (scheduled time passed)..."
            self.button_main.IsEnabled = False
            # Small delay to show the message
            time.sleep(2)
        else:
            # Show waiting message
            self.button_main.Content = "Waiting for scheduled time..."
            self.button_main.IsEnabled = False
            
            # Wait until the scheduled time
            while datetime.now() < target_time:
                remaining = target_time - datetime.now()
                remaining_minutes = int(remaining.total_seconds() // 60)
                remaining_seconds = int(remaining.total_seconds() % 60)
                
                self.button_main.Content = "Waiting... {}m {}s remaining".format(
                    remaining_minutes, remaining_seconds
                )
                NOTIFICATION.messenger("Waiting... {}m {}s remaining".format(
                    remaining_minutes, remaining_seconds
                ))
                time.sleep(1)
        
        # Time reached, sync document first
        NOTIFICATION.messenger("Scheduled time reached. Syncing document before starting export...")
        # Sync document without closing it
        REVIT_SYNC.sync_and_close(close_others=False)
        
        # Reset button
        self.button_main.Content = "Starting export..."
        self.button_main.IsEnabled = True


    def update_time_estimate(self):

        for doc in self.docs_to_process:
            self.record = self.get_time_estimate_from_record(doc)
            for item in self.data_grid_preview.ItemsSource:
                if DataGridDocIdMapObj.get_central_doc_name(item.item.Document) != DataGridDocIdMapObj.get_central_doc_name(doc):
                    continue
                self.record["{}#{}".format(item.item.UniqueId, item.extension)] = item.time_estimate

            record_file = self.get_record_file_by_doc(doc)
            DATA_FILE.set_data(self.record, record_file, is_local=False)


    def get_time_estimate_from_record(self, doc):
        record_file = self.get_record_file_by_doc(doc)
        return DATA_FILE.get_data(record_file, is_local=False)



    def get_record_file_by_doc(self, doc):
        return "EXPORT_RECORD_" + DataGridDocIdMapObj.get_central_doc_name(doc) 

 
    

def get_doc_path(doc):
    if doc.IsWorkshared:
        return doc.GetWorksharingCentralModelPath()
    else:
        return doc.PathName

    
@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def ennead_exporter():
    window = SuperExporter()
    window.ShowDialog()




################## main code below #####################
if __name__ == "__main__":
    output = script.get_output()
    output.close_others()

    ennead_exporter()







