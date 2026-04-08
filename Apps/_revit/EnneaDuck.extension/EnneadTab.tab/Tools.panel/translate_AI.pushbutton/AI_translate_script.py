#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Multi-language translation assistant for your Revit project. Translate sheet names and view names between 10 languages (Chinese, Japanese, Korean, Spanish, French, Italian, German, Portuguese, Arabic, and more). Uses architecture-specific terminology with structured AI output and approval workflow before applying changes."
__title__ = "AI\nTranslate"
__post_link__ = "https://ei.ennead.com/_layouts/15/Updates/ViewPost.aspx?ItemID=29679"
__youtube__ = "https://youtu.be/7dlOneO2Mts"
__tip__ = True
__is_popular__ = True
from Autodesk.Revit.UI import IExternalEventHandler, ExternalEvent # pyright: ignore 
from Autodesk.Revit.Exceptions import InvalidOperationException # pyright: ignore 
from Autodesk.Revit import DB # pyright: ignore 
from Autodesk.Revit import UI # pyright: ignore

from pyrevit.forms import WPFWindow
from pyrevit import script, forms

import traceback
import System # pyright: ignore 
import time
import difflib

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, AUTH, AI, JOKE, ENVIRONMENT, NOTIFICATION, DATA_FILE, FOLDER, SOUND, LOG
from EnneadTab.REVIT import REVIT_APPLICATION, REVIT_FORMS

# .NET HTTP for reliable HTTPS from IronPython (urllib2 SSL is broken)
import clr # pyright: ignore
clr.AddReference("System") # pyright: ignore
import json






uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()
__persistentengine__ = True


def translate_contents(data, para_name):
    print ("firing... ext event")
    t = DB.Transaction(doc, "Translate")
    t.Start()

    success_count = 0
    failed_count = 0
    for item in data:
        if not item.is_approved:
            continue


        sheet = doc.GetElement(item.id)
        current_translation = sheet.LookupParameter(para_name).AsString()
        if current_translation == item.chinese_name:
            print ("Existing translation to <{}> is the same version as the approved one.".format(item.english_name))
            failed_count += 1
            continue

        print ("Adding translation to <{}>".format(item.english_name))
        if sheet.LookupParameter(para_name).IsReadOnly:
            print ("The translation parameter for {} is read-only.".format(output.linkify(sheet.Id, title = item.english_name)))
            failed_count += 1
            continue
        sheet.LookupParameter(para_name).Set(item.chinese_name)
        success_count += 1
    t.Commit()
    REVIT_FORMS.notification(main_text = "Approved translation added to sheets.\nYou may add other sheets or exit the window.",
                                            sub_text = "{} translation added/modified.\n{} sheet skipped due to existing translation matching approved version, or tranlation parameter locked by template.".format(success_count, failed_count))


# Create a subclass of IExternalEventHandler
class SimpleEventHandler(IExternalEventHandler):
    """
    Simple IExternalEventHandler sample
    """

    # __init__ is used to make function from outside of the class to be executed by the handler. \
    # Instructions could be simply written under Execute method only
    def __init__(self, do_this):
        self.do_this = do_this
        self.kwargs = None
        self.OUT = None


    # Execute method run in Revit API environment.
    def Execute(self,  uiapp):
        try:
            try:
                #print "try to do event handler func"
                self.OUT = self.do_this(*self.kwargs)
            except:
                print ("failed")
                print (traceback.format_exc())
        except InvalidOperationException:
            # If you don't catch this exeption Revit may crash.
            print ("InvalidOperationException catched")

    def GetName(self):
        return "simple function executed by an IExternalEventHandler in a Form"



class DataGridObj(object):
    def __init__(self, element_id, chinese_name = None, is_approved = False):
        self.id = element_id
        element = doc.GetElement(element_id)
        if isinstance(element, DB.ViewSheet):
            self.english_name = element.Name
            self.sheet_num = element.SheetNumber
        else:
            title_para_id = DB.BuiltInParameter.VIEW_DESCRIPTION
            title = element.Parameter[title_para_id].AsString()
            if len(title) > 0:
                self.english_name = title
            else:
                self.english_name = element.Name
            self.sheet_num = element.LookupParameter("Sheet Number").AsString()

        self.chinese_name = chinese_name
        self.is_approved = is_approved


# A simple WPF form used to call the ExternalEvent
class AiTranslator(WPFWindow):
    """
    Simple modeless form sample
    """

    def pre_actions(self):

        self.revit_update_event_handler = SimpleEventHandler(translate_contents)
        self.ext_event = ExternalEvent.Create(self.revit_update_event_handler)

        return

    def __init__(self):
        self.pre_actions()

        xaml_file_name = "AiTranslator.xaml" ###>>>>>> if change from window to dockpane, the top level <Window></Window> need to change to <Page></Page>
        WPFWindow.__init__(self, xaml_file_name)

        self.title_text.Text = "EnneadTab AI Translator"

        self.sub_text.Text = "Translate sheet names and apply changes to Revit."

        self.instruction_step_text.Text = "\t-Step 1:\n\n\t-Step 2:\n\t-Step 3:\n\n\n\t-Step 4:"

        self.instruction_text.Text = "Pick sheets. For performance reason, please limit the amount of sheets to translate.\n(Recommending less than 100 sheets.)\nTranslate sheets.\nMake edits to the results by editing in the table if needed. When you are happy with some or all the result, click 'approve' checkbox to lock this version. Once approved, the translation will not change if you try to run translate again.\nApply approved translation to Revit."

        self.Title = self.title_text.Text

        self.set_image_source(self.logo_img, "{}\logo_vertical_light.png".format(ENVIRONMENT.IMAGE_FOLDER))
        self.translation_para_name.Text = "MC_$Translate"
        self.radial_bt_do_sheets.IsChecked = True
        self.mode = "Sheets"

        # Language selector
        self.LANGUAGES = [
            ("Chinese (Simplified)", "zh-CN"),
            ("Chinese (Traditional)", "zh-TW"),
            ("Japanese", "ja"),
            ("Korean", "ko"),
            ("Spanish", "es"),
            ("French", "fr"),
            ("Italian", "it"),
            ("German", "de"),
            ("Portuguese", "pt"),
            ("Arabic", "ar"),
        ]
        for display_name, _ in self.LANGUAGES:
            self.language_selector.Items.Add(display_name)
        self.language_selector.SelectedIndex = 0  # Default: Chinese (Simplified)
        self.target_language_code = "zh-CN"
        self.target_language_name = "Chinese (Simplified)"

        self.update_category_header()

        self.Show()




    @ERROR_HANDLE.try_catch_error()
    def pick_views_sheets_Click(self, sender, e):

        if not self.is_translation_para_valid():
            return

        if self.radial_bt_do_sheets.IsChecked:

            selected_elements = forms.select_sheets(title = "Select {} to translate".format(self.mode),
                                                    button_name = "Select {} to translate".format(self.mode))


        else:

            all_elements = DB.FilteredElementCollector(doc).OfClass(DB.View).WhereElementIsNotElementType().ToElements()
            all_elements = list(all_elements)


            all_elements.sort(key = lambda x: x.Name)



            def is_good_view(x):
                if x.IsTemplate:
                    return False
                if "revision schedule" in x.Name.lower():
                    return False
                if x.ViewType not in [DB.ViewType.FloorPlan,
                                DB.ViewType.CeilingPlan,
                                DB.ViewType.Elevation,
                                DB.ViewType.ThreeD,

                                DB.ViewType.DraftingView,
                                DB.ViewType.Legend,
                                DB.ViewType.AreaPlan,
                                DB.ViewType.Section,
                                DB.ViewType.Detail]:
                    return False
                return  x.LookupParameter("Sheet Number").AsString() != "---"
       

            all_elements = filter(is_good_view, all_elements)



            selected_elements = forms.SelectFromList.show(all_elements,
                                                        multiselect = True,
                                                        title = "Select {} to translate".format(self.mode),
                                                        button_name = "Select {} to translate".format(self.mode),
                                                        name_attr = "Name")





        if not selected_elements:
            return

        para_name = self.translation_para_name.Text

        def new_item(x):
            if not x.LookupParameter(para_name):
                return  DataGridObj(x.Id, chinese_name = "---", is_approved = True)

            current_translation = x.LookupParameter(para_name).AsString()

            if not current_translation or len(current_translation) == 0:
                return DataGridObj(x.Id)
            return DataGridObj(x.Id, chinese_name = current_translation, is_approved = True)
        self.data_grid.ItemsSource = [new_item(x) for x in selected_elements]
        self.data_grid.Visibility = System.Windows.Visibility.Visible

        self.bt_translate_sheet.Visibility = System.Windows.Visibility.Visible
        self.bt_apply_translation.Visibility = System.Windows.Visibility.Visible
        self.bt_open_recent.Visibility = System.Windows.Visibility.Visible
        self.bt_approve_selected.Visibility = System.Windows.Visibility.Visible
        self.bt_unapprove_selected.Visibility = System.Windows.Visibility.Visible



    @ERROR_HANDLE.try_catch_error()
    def translate_views_sheets_Click(self, sender, e):
        # This Raise() method launch a signal to Revit to tell him you want to do something in the API context
        """dummy"""
        temp = []
        for item in self.data_grid.ItemsSource:
            if item.is_approved:
                temp.append(item)
            else:
                item.chinese_name = "translating..." + item.english_name
                temp.append(DataGridObj(item.id, item.chinese_name))

        self.data_grid.ItemsSource = temp

        """real"""
        lookup_map = []

        for item in self.data_grid.ItemsSource:
            if not item.is_approved:
                lookup_map.append(item.english_name)

        if len(lookup_map) == 0:
            self.debug_textbox.Text = "There is nothing to translate."
            REVIT_FORMS.notification(main_text = "There is nothing to translate.", sub_text = "Everything is approved.")
            return

        # 2026-04-08: Use structured JSON output instead of >> parsing.
        # Send list of English names, get back {english: translation} dict.
        result = self.fire_AI_translator(lookup_map, len(lookup_map))

        if not result:
            return

        # result is a dict {english_name: translation}
        data = result
        self.recent_translation = ["##Below are the recent translations, you can pick to copy-paste into the Translator Table."]
        for v in data.values():
            self.recent_translation.append(v)

        temp = []
        failed_count = 0
        success_count = 0
        for item in self.data_grid.ItemsSource:
            if item.is_approved:
                temp.append(item)
            else:
                translation = data.get(item.english_name)
                if translation:
                    temp.append(DataGridObj(item.id, translation))
                    success_count += 1
                else:
                    print ("---Cannot find translation for: {}".format(item.english_name))
                    temp.append(DataGridObj(item.id, "Skipped Translation"))
                    failed_count += 1

        self.data_grid.ItemsSource = temp
        if failed_count:
            self.debug_textbox.Text = "Some items were not translated. You can try again.\nTip: Approve the ones you like to reduce batch size."
            REVIT_FORMS.notification(main_text = "Translation success = {}\nTranslation skipped = {}".format(success_count, failed_count), sub_text = "You can ask to translate again.\nApprove the ones you like so far to reduce batch size.")


    @ERROR_HANDLE.try_catch_error()
    def is_translation_para_valid(self):
        para_name = self.translation_para_name.Text

        if self.radial_bt_do_sheets.IsChecked:
            DB_class = DB.ViewSheet

        else:
            DB_class = DB.ViewPlan

        element = DB.FilteredElementCollector(doc).OfClass(DB_class).WhereElementIsNotElementType().FirstElement ()


        if not element.LookupParameter(para_name):
            REVIT_FORMS.notification(main_text = "Cannot find parameter with this name.",
                                                    sub_text = "Are you sure <{}> if a valid parameter for sheets? You can modify what is used to store translation in the lower-right textbox".format(para_name))
            return False
        return True

    #@ERROR_HANDLE.try_catch_error()
    def apply_translation_Click(self, sender, e):
        para_name = self.translation_para_name.Text

        if not self.is_translation_para_valid():
            return



        self.revit_update_event_handler.kwargs = self.data_grid.ItemsSource, para_name
        self.ext_event.Raise()
        res = self.revit_update_event_handler.OUT
        if res:
            self.debug_textbox.Text = res
        else:
            self.debug_textbox.Text = "Debug Output:"

    @ERROR_HANDLE.try_catch_error()
    def open_recent_Click(self, sender, e):
        if not hasattr(self, "recent_translation"):
            NOTIFICATION.messenger(main_text = "No recent translation found.")
            return
        
        filepath = FOLDER.get_local_dump_folder_file("Recent Translation.txt")
        DATA_FILE.set_list(self.recent_translation, filepath, end_with_new_line = False)
        import os
        os.startfile(filepath)


    def approve_selected_Click(self, sender, e):
        self.change_approve_selected(as_approve = True)

    def unapprove_selected_Click(self, sender, e):
        self.change_approve_selected(as_approve = False)

    @ERROR_HANDLE.try_catch_error()
    def language_changed(self, sender, e):
        idx = self.language_selector.SelectedIndex
        if idx < 0 or idx >= len(self.LANGUAGES):
            return
        self.target_language_name, self.target_language_code = self.LANGUAGES[idx]
        # Update column header
        self.translation_column.Header = "{} (Editable in Table)".format(self.target_language_name)
        # Show/hide sample translation settings (only useful for Chinese)
        is_chinese = self.target_language_code in ("zh-CN", "zh-TW")

    def change_approve_selected(self, as_approve):


        temp = []
        for i, item in enumerate(self.data_grid.ItemsSource):
            if item in self.data_grid.SelectedItems:
                approve = as_approve
            else:
                approve = item.is_approved
            temp.append( DataGridObj(item.id, item.chinese_name, approve))
        self.data_grid.ItemsSource = temp

    @ERROR_HANDLE.try_catch_error()
    def change_UI_translate_mode(self, sender, e):


        if "sheets" in self.radial_bt_do_sheets.Content.lower() and self.radial_bt_do_sheets.IsChecked:
            # nothing changed
            return

        if "views" in self.radial_bt_do_sheets.Content.lower() and not self.radial_bt_do_sheets.IsChecked:
            # nothing changed
            return


        if self.radial_bt_do_sheets.IsChecked:
            self.mode = "Sheets"

        else:
            self.mode = "Views"

        self.bt_pick.Content = "Pick {}".format(self.mode)
        self.bt_translate_sheet.Content = "  Translate UnApproved {}  ".format(self.mode)
        self.bt_apply_translation.Content = "  Applied Approved Translation To {}  ".format(self.mode)
        self.data_grid.ItemsSource = []

    @ERROR_HANDLE.try_catch_error()
    def change_UI_sample_category(self, sender, e):
        if self.is_include_sample_systems.IsChecked:
            self.is_include_sample_plans.IsChecked = True
            self.is_include_sample_elevations.IsChecked = True
            self.is_include_sample_sections.IsChecked = True


        if self.is_include_sample_G_series.IsChecked:
            self.is_include_sample_schedules.IsChecked = True

        self.update_category_header()

    def update_category_header(self):
        samples = self.get_sample_translation_dict()

        count = 0
        for key,value in samples.items():
            if key == "xxx":
                continue
            count += 1
        self.category_header.Text = "Limit your sample translation can help increase capacity. Current Sample: {}".format(count)


    def close_Click(self, sender, e):
        # This Raise() method launch a signal to Revit to tell him you want to do something in the API context
        self.Close()

    def mouse_down_main_panel(self, sender, args):
        #print "mouse down"
        sender.DragMove()

    @ERROR_HANDLE.try_catch_error()
    def selective_user_sample_Click(self, sender, e):
        # This Raise() method launch a signal to Revit to tell him you want to do something in the API context
        samples = self.get_sample_translation_dict_from_user(use_predefined = False)
        if not samples:
            return

        class MyOption(forms.TemplateListItem):
            @property
            def name(self):
                return "{} >> {}".format(self.item, samples[self.item])
        opts = [MyOption(x) for x in samples.keys()]
        opts.sort(key = lambda x: x.name)
        selected = forms.SelectFromList.show(opts,
                                            multiselect = True,
                                            title = "Pick other approved translation")
        if not selected:
            self.user_samples = samples
            return

        self.user_samples = dict()
        for key in selected:
            self.user_samples[key] = samples[key]






    #@ERROR_HANDLE.try_catch_error()
    def fire_AI_translator(self, new_prompt, request_count):
        """Call EnneadTab AI proxy via .NET HttpWebRequest (IronPython HTTPS).

        # 2026-04-08: Uses .NET System.Net.HttpWebRequest for reliable HTTPS
        # from IronPython. Python urllib2 SSL is broken in IronPython 2.7.
        # Calls enneadtab.com/api/ai/desktop-chat with Gemini backend.
        """
        session_token = AUTH.get_token()
        if not session_token:
            if not AUTH.is_auth_in_progress():
                AUTH.request_auth()
            # Wait for browser auth to complete (polling file cache)
            max_wait = 120
            elapsed = 0
            while elapsed < max_wait:
                self.debug_textbox.Text = "Waiting for browser sign-in... {}s/{}s".format(elapsed, max_wait)
                time.sleep(1)
                elapsed += 1
                session_token = AUTH.get_token()
                if session_token:
                    break
            if not session_token:
                self.debug_textbox.Text = "Sign-in timed out. Please try again."
                return None

        # Build sample translations for context
        target_lang = self.target_language_name
        sample_translate = ""

        # Use built-in samples for the selected language
        lang_samples = self.get_sample_translation_dict_for_language(self.target_language_code)
        for key, value in lang_samples.items():
            if key == "xxx":
                continue
            sample_translate += "\n{} >> {}".format(key, value)

        if self.is_including_user_sample.IsChecked:
            user_samples = self.get_sample_translation_dict_from_user()
            if user_samples:
                for key, value in user_samples.items():
                    sample_translate += "\n{} >> {}".format(key, value)

        mode_context = u"SHEET NAMES (title block text)" if self.mode == "Sheets" else u"VIEW NAMES (plan/section/elevation/detail view titles in the project browser)"
        arch_context = (
            u"You are an expert architectural translator working for an international architecture firm. "
            u"You are translating {} from Autodesk Revit. ".format(mode_context)
            + u"These are NOT general text -- they are standardized terms used in the AEC (Architecture, Engineering, Construction) industry. "
            u"Use the OFFICIAL architectural terminology that licensed architects and engineers in the target country would use on real construction document sets. "
            u"Key terms: 'SECTION' = a cut-through view of a building (not a generic 'part'). "
            u"'ELEVATION' = exterior face view of a building. 'REFLECTED CEILING PLAN' = looking up at the ceiling, drawn as if reflected in a mirror on the floor. "
            u"'SYSTEM DRAWINGS' = curtain wall or facade assembly details. 'PARTITION' = interior wall dividing spaces. "
            u"'SLAB EDGE' = floor slab perimeter detail. 'RCP' = Reflected Ceiling Plan. "
            u"Level names like 'LEVEL 1', 'BASEMENT', 'MEZZANINE', 'ROOF' should use the local architectural convention. "
            u"Building codes references ('FIRE COMPARTMENT', 'REFUGE FLOOR', 'EGRESS') should use the target country's building code terminology. "
            u"Prioritize industry-standard terms over literal word-for-word translation. "
            u"If the target language has an established convention (e.g. JIS for Japanese, KS for Korean, DIN for German, NF for French), follow it."
        )
        json_instruction = (
            u"Return a JSON object where each key is the original English name and "
            u"the value is the translation. Example: "
            u'{{"FLOOR PLAN": "...", "ROOF PLAN": "..."}}'
        )
        if sample_translate:
            system_prompt = u"{}\n\nTranslate from English to {}. Reference examples:\n{}\n\n{}".format(arch_context, target_lang, sample_translate, json_instruction)
        else:
            system_prompt = u"{}\n\nTranslate from English to {}.\n\n{}".format(arch_context, target_lang, json_instruction)

        # Send as JSON list for clean structured input
        user_message = json.dumps(new_prompt, ensure_ascii=True)

        self.debug_textbox.Text = "Sending translation request..."

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            ai_response = AI.chat_with_token(session_token, messages, temperature=0.3, json_mode=True)
        except AI.AIRequestError as e:
            error_msg = str(e)
            print("Translation error: {}".format(error_msg))

            if e.status_code == 401:
                AUTH.clear_token()
                self.debug_textbox.Text = "Token expired. Please try translating again."
                return None

            self.debug_textbox.Text = "Cannot get response from the EnneadTab Server."
            REVIT_FORMS.notification(
                main_text="AI translation failed.",
                sub_text="Error: {}\n\nConsider reducing the number of things to translate.".format(error_msg)
            )
            return None

        # Parse structured JSON response
        try:
            data = json.loads(ai_response)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object, got {}".format(type(data)))
        except Exception as e:
            print("Failed to parse JSON response: {}".format(e))
            print("Raw response: {}".format(ai_response))
            self.debug_textbox.Text = "Translation response was not in expected format. Try again."
            return None

        SOUND.play_sound("sound_effect_popup_msg3.wav")
        self.debug_textbox.Text = "Translation finished. {} items translated.".format(len(data))
        return data

    def get_sample_translation_dict_from_user(self, use_predefined = True):
        if use_predefined and hasattr(self, "user_samples"):
            return self.user_samples

        if not self.data_grid.ItemsSource:
            return

        samples = dict()
        for item in self.data_grid.ItemsSource:
            if item.is_approved and len(item.chinese_name) != 0:
                samples[item.english_name] = item.chinese_name
        return samples


    def get_sample_translation_dict_for_language(self, lang_code):
        """Get sample translations for the selected language.

        For Chinese (zh-CN), returns the full existing sample dict.
        For CJK languages (zh-TW, ja, ko), returns Unicode-escaped samples.
        For Latin/Arabic languages, no samples needed -- Gemini handles them
        natively without examples. Avoids IronPython Unicode source encoding issues.
        """
        if lang_code == "zh-CN":
            return self.get_sample_translation_dict()
        if lang_code == "zh-TW":
            samples = dict()
            samples["SITE PLAN"] = u"\u5834\u5730\u5e73\u9762\u5716"
            samples["FLOOR PLAN"] = u"\u5e73\u9762\u5716"
            samples["ROOF PLAN"] = u"\u5c4b\u9802\u5e73\u9762\u5716"
            samples["REFLECTED CEILING PLAN"] = u"\u53cd\u5c04\u5929\u82b1\u5e73\u9762\u5716"
            samples["BUILDING ELEVATIONS"] = u"\u5efa\u7bc9\u7acb\u9762\u5716"
            samples["BUILDING SECTIONS"] = u"\u5efa\u7bc9\u5256\u9762\u5716"
            samples["COVER SHEET"] = u"\u5c01\u9762"
            samples["DRAWING LIST"] = u"\u5716\u7d19\u76ee\u9304"
            samples["DETAIL"] = u"\u8a73\u5716"
            return samples
        if lang_code == "ja":
            samples = dict()
            samples["SITE PLAN"] = u"\u914d\u7f6e\u56f3"
            samples["FLOOR PLAN"] = u"\u5e73\u9762\u56f3"
            samples["ROOF PLAN"] = u"\u5c4b\u6839\u4f0f\u56f3"
            samples["REFLECTED CEILING PLAN"] = u"\u5929\u4e95\u4f0f\u56f3"
            samples["BUILDING ELEVATIONS"] = u"\u7acb\u9762\u56f3"
            samples["BUILDING SECTIONS"] = u"\u65ad\u9762\u56f3"
            samples["COVER SHEET"] = u"\u8868\u7d19"
            samples["DRAWING LIST"] = u"\u56f3\u9762\u30ea\u30b9\u30c8"
            samples["DETAIL"] = u"\u8a73\u7d30\u56f3"
            return samples
        if lang_code == "ko":
            # Verified by DaYeon Kim (Korean architect) 2026-04-08
            samples = dict()
            samples["SITE PLAN"] = u"\ubc30\uce58\ub3c4"
            samples["SITE GROUND PLAN"] = u"\ub300\uc9c0 \uc9c0\uc0c11\uce35 \ud3c9\uba74\ub3c4"
            samples["FLOOR PLAN"] = u"\ud3c9\uba74\ub3c4"
            samples["ROOF PLAN"] = u"\uc9c0\ubd95 \ud3c9\uba74\ub3c4"
            samples["REFLECTED CEILING PLAN"] = u"\ucc9c\uc815 \ud3c9\uba74\ub3c4"
            samples["BUILDING ELEVATIONS"] = u"\uc785\uba74\ub3c4"
            samples["BUILDING SECTIONS"] = u"\ub2e8\uba74\ub3c4"
            samples["COVER SHEET"] = u"\ud45c\uc9c0"
            samples["DRAWING LIST"] = u"\ub3c4\uba74 \ubaa9\ub85d"
            samples["DETAIL"] = u"\uc0c1\uc138\ub3c4"
            samples["EXTERIOR WALL SYSTEMS"] = u"\uc678\ubcbd \uc2dc\uc2a4\ud15c"
            samples["EXTERIOR WALL SECTIONS"] = u"\uc678\ubcbd\ub2e8\uba74\ub3c4"
            samples["PARTITION TYPES"] = u"\ud30c\ud2f0\uc158 \ud0c0\uc785 \uc77c\ub78c\ud45c"
            samples["PARTITION DETAILS"] = u"\ud30c\ud2f0\uc158 \uc0c1\uc138\ub3c4"
            samples["CEILING DETAILS"] = u"\ucc9c\uc815 \uc0c1\uc138\ub3c4"
            return samples
        # Latin-script and Arabic languages: Gemini handles these natively
        # without examples. No samples avoids IronPython Unicode encoding issues.
        return dict()


    def get_sample_translation_dict(self):
        sample_type_g_series = self.is_include_sample_G_series.IsChecked
        sample_type_schedules = self.is_include_sample_schedules.IsChecked
        sample_type_floor_plans = self.is_include_sample_plans.IsChecked
        sample_type_floor_plans_additional = self.is_include_sample_plans_additional.IsChecked
        sample_type_elevations = self.is_include_sample_elevations.IsChecked
        sample_type_elevations_additional = self.is_include_sample_elevations_additional.IsChecked
        sample_type_sections = self.is_include_sample_sections.IsChecked
        sample_type_systems = self.is_include_sample_systems.IsChecked
        sample_type_systems_additional = self.is_include_sample_systems_additional.IsChecked
        sample_type_geo_plans = self.is_include_sample_geo_plans.IsChecked
        sample_type_details = self.is_include_sample_details.IsChecked
        sample_type_rcps = self.is_include_sample_rcps.IsChecked
        sample_type_miscs = True


        samples = dict()

        #basic syntax
        #samples["SITE"] = u"场地"




        if sample_type_g_series:
            samples["COVER SHEET"] = u"封面"
            samples["NARRATIVE"] = u"设计说明"
            samples["RENDERING"] = u"效果图"
            samples["MATERIAL INDEX"] = u"材料列表"
            samples["SITE CIRCULATION ANALYSIS"] = u"场地动线分析图"
            samples["FRONTAGE RATIO"] = u"贴线率"



        if sample_type_schedules:
            samples["DRAWING LIST"] = u"图纸目录"


        if sample_type_floor_plans:
            samples["N3 - LEVEL 10 & 11 REFUGE FLOOR PLAN"] = u"建筑N3十层与十一层避难层平面图"
            samples["BASEMENT LEVEL 2 FLOOR PLAN"] = u"地下二层平面图"
            samples["Ground Floor Plan"] = u"首层平面图"
            samples["OVERALL SITE PLAN"] = u"总平面"
            samples["OVERALL 2 FLOOR PLAN"] = u"二层总体平面图"
            samples["LEVEL 5 & 6  FLOOR PLAN"] = u"五及六层平面图"
            samples["MEP ROOF FLOOR PLAN & ROOF PLAN"] = u"屋顶机房及屋顶平面图"


        if sample_type_floor_plans_additional:
            samples["N3 - MEP ROOF PLAN & ROOF PLAN"] = u"建筑N3屋顶机房平面图"
            samples["N5 - LEVEL 22 & 23  FLOOR PLAN"] = u"建筑N5二十二层与二十三层平面图"
            samples["LEVEL 26 - 28 FLOOR PLAN"] = u"二十六至二十八层平面图"
            samples["FLOOR PLAN - ROOF/MEZZANINE LEVEL"] = u"屋顶及夹层平面图"
            samples["B1 FIRE COMPARTMENT PLAN"] = u"B1防火分隔平面图"


        if sample_type_elevations:
            samples["ELEVATIONS EAST & WEST"] = u"东，西立面图"
            samples["N3 - ELEVATION EAST"] = u"建筑N3 东立面图"
            samples["SITE ELEVATIONS EAST & WEST"] = u"场地东，西立面图"
            samples["N3 - PARTIAL ELEVATIONS - TOWER"] = u"建筑N3 塔楼局部立面图"

        if sample_type_elevations_additional:
            samples["N3 - PARTIAL ELEVATIONS - PODIUM"] = u"建筑N3 裙楼局部立面图"
            samples["Enlarged Elevation"] = u"放大立面图"


        if sample_type_sections:
            samples["N3 - SECTION E-W"] = u"建筑N3 东，西剖面图"
            samples["SECTION"] = u"剖面图"

        if sample_type_geo_plans:
            samples["GEOMETRY PLAN - LEVEL 1"] = u"几何定位图首层"
            samples["GEOMETRY PLAN - ROOF/MEZZANINE LEVEL"] = u"几何定位图屋顶及夹层"
            samples["GEOMETRY PLAN - LEVEL 10,12,13,14"] = u"建筑几何定位图 十层、十二至十四层"
            samples["GEOMETRY PLAN - LEVEL 15,16,17,18"] = u"建筑几何定位图 十五至十八层"

        if sample_type_systems:
            samples["CW-1 SYSTEM DRAWINGS"] = u"主立面CW-1外墙系统"
            samples["CW-2 RECESS FACADE DETAILS TYP"] = u"CW-2退面幕墙系统详图"
            samples["CW-1 & CW-2 ENLARGED DRAWINGS - PARAPET"] = u"CW-1与CW-2幕墙系统-女儿墙"
            samples["SF-1 ENLARGED DRAWINGS - SUNKEN PLAZA"] = u"沿街立面SF-1幕墙系统下沉广场"
            samples["SKY-1 ENLARGED DRAWINGS - SKYLIGHTS"] = u"SKY-1天窗系统"
            samples["N4 - TOWER CW-1 SYSTEM DRAWINGS"] = u"建筑N4塔楼CW-1主立面外墙系统"
            samples["PODIUM CW-5/CW-5A SYSTEM DRAWINGS"] = u"裙楼CW-5/CW-5A 主立面外墙系统"

        if sample_type_systems_additional:
            samples["CW-2 PARTIAL PERSPECTIVE"] = u"CW-2 局部透视图"
            samples["CW-4A ENLARGED PLAN - LEVEL 8"] = u"CW-4A 放大平面 - 八层平面"
            samples["CW-7A ENLARGED SECTION"] = u"CW-7A 放大剖面"
            samples["CW-5A ENLARGED PLAN - TRANSITION TO CW-4"] = u"CW-5A 放大平面 - 与CW-4交接口"
            samples["SUNKEN COURTYARD ENLARGED REFLECTED CEILING PLAN"] = u"下沉广场放大吊顶平面"
            samples["RETAIL SE ENTRY SF-1 ENLARGED SECTION"] = u"商业东南入口放大剖面"
            samples["SKY-1 ENLARGED NORTH ELEVATION"] = u"采光天窗-1 放大北立面"
            samples["xxx"] = u"xxx"
            samples["xxx"] = u"xxx"
            samples["xxx"] = u"xxx"
            samples["xxx"] = u"xxx"
            samples["xxx"] = u"xxx"




        if sample_type_details:
            samples["SKY-1 & MP-6 FACADE DETAILS"] = u"天窗SKY-1及金属板MP-6幕墙系统详图"
            samples["CANOPY/VESTIBULE FACADE DETAILS"] = u"雨棚及门厅详图"
            samples["ENTRANCE FACADE DETAILS"] = u"入口幕墙节点"
            samples["CW-3 FACADE DETAILS TYP"] = u"CW-3外幕墙系统详图"
            samples["ST-1 FACADE DETAILS"] = u"ST-1主幕墙石墙系统详图"
            samples["CW-5A ENLARGED PLAN - TRANSITION TO CW-4"] = u"CW-5A 放大平面 - 与CW-4交接口"
            samples["CW-1 TYP. SLAB EDGE"] = u"CW-1 板边标准节点"
            samples["TYP. BALCONY DETAIL @ DEPRESSED SLAB"] = u"降板区标准露台节点"
            samples["GLASS LOUVER @ REFUGE FLOOR"] = u"避难层玻璃百页"
            samples["TYP. PARAPET COPING DETAIL"] = u"女儿墙顶部标准节点"
            samples["CW-3 GLASS FIN PLAN DETAIL@ LEVEL 1 LOBBY"] = u"CW-3 首层大堂弧面转角处玻璃肋平面节点"
            samples["PLAN DETAIL @ TYP. GUARDRAIL"] = u"CW-4 标准栏杆平面节点"
            samples["ST-1 PLAN DETAIL @ EGRESS DOOR"] = u"ST-1 疏散门平面节点"



        if sample_type_rcps:
            samples["LEVEL 1 & 2 RCP"] = u"反射吊顶平面一二层"
            samples["LEVEL 1 REFLECTED CEILING PLAN"] = u"一层反射天花平面"
            samples["SUNKEN COURTYARD ENLARGED REFLECTED CEILING PLAN"] = u"下沉广场放大吊顶平面"

        if sample_type_miscs:
            samples["POWER STATION DRAWINGS"] = u"变电站图纸"
            samples["RAMP AND SUPPORT"] = u"坡道及支撑件"


        return samples


        samples["xxx"] = u"xxx"








@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    AiTranslator()
    


################## main code below #####################
output = script.get_output()
output.close_others()
output.set_width(1)
output.set_height(1)


if __name__ == "__main__":
    main()


