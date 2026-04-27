#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Multi-language translation assistant for your Revit project. Translate sheet names and view names between 15 languages (Chinese, Japanese, Korean, Spanish, French, Italian, German, Portuguese, Arabic, Hebrew, Persian, Turkish, Hindi, Marathi). Uses authority-backed AEC terminology (CSTT, BIS, DIN, NF DTU, UNI, CTE, SBC, Aramco SAES, TSE, Maharashtra Shabdakosh, Israel Architects Assoc., Iran NBR) with structured AI output and approval workflow before applying changes."
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
import re


# RTL languages: Arabic, Hebrew, Persian/Farsi, Urdu. Revit has known
# bidi/shaping bugs in title block LABELS specifically (Autodesk KB confirms
# Arabic shifts on AutoCAD export, Hebrew character reorder on edit).
# Schedules and TextNotes behave better. Do NOT pre-shape with arabic-reshaper
# -- Revit/Windows GDI does its own shaping; pre-shaping causes double-shape.
RTL_LANG_CODES = ("ar", "he", "fa", "ur")

# Map Persian/Eastern Arabic-Indic digits to Western. Gemini may return
# native digits for Farsi; Revit title blocks usually expect Western digits.
_PERSIAN_DIGIT_MAP = {
    u"۰": u"0", u"۱": u"1", u"۲": u"2", u"۳": u"3", u"۴": u"4",
    u"۵": u"5", u"۶": u"6", u"۷": u"7", u"۸": u"8", u"۹": u"9",
    u"٠": u"0", u"١": u"1", u"٢": u"2", u"٣": u"3", u"٤": u"4",
    u"٥": u"5", u"٦": u"6", u"٧": u"7", u"٨": u"8", u"٩": u"9",
}

# Unicode bidi controls: wrap RTL run when string mixes RTL with Latin/digits
# so Revit's bidi algorithm orders the segments correctly.
_RLE = u"‫"  # RIGHT-TO-LEFT EMBEDDING
_PDF = u"‬"  # POP DIRECTIONAL FORMATTING
_RTL_CHAR_RANGE = re.compile(u"[֐-׿؀-ۿ܀-ݏﭐ-﷿ﹰ-﻿]")
_LATIN_OR_DIGIT_RANGE = re.compile(u"[A-Za-z0-9]")


def normalize_for_revit(text, lang_code):
    """Preprocess translated string before writing to a Revit parameter.

    For RTL languages: normalize Persian/Arabic-Indic digits to Western, and
    wrap the string in Unicode bidi controls when it mixes RTL with Latin
    characters or digits (e.g., 'A-101 + Arabic name').
    """
    if not text:
        return text
    text = text.strip().lstrip(u"﻿")
    if lang_code not in RTL_LANG_CODES:
        return text
    if lang_code == "fa":
        for src, dst in _PERSIAN_DIGIT_MAP.items():
            text = text.replace(src, dst)
    has_rtl = _RTL_CHAR_RANGE.search(text) is not None
    has_latin = _LATIN_OR_DIGIT_RANGE.search(text) is not None
    if has_rtl and has_latin and not text.startswith(_RLE):
        text = _RLE + text + _PDF
    return text






uidoc = REVIT_APPLICATION.get_uidoc()
doc = REVIT_APPLICATION.get_doc()
__persistentengine__ = True


def translate_contents(data, para_name, lang_code):
    print ("firing... ext event")
    t = DB.Transaction(doc, "Translate")
    t.Start()

    success_count = 0
    failed_count = 0
    for item in data:
        if not item.is_approved:
            continue


        sheet = doc.GetElement(item.id)
        normalized = normalize_for_revit(item.chinese_name, lang_code)
        current_translation = sheet.LookupParameter(para_name).AsString()
        if current_translation == normalized:
            print ("Existing translation to <{}> is the same version as the approved one.".format(item.english_name))
            failed_count += 1
            continue

        print ("Adding translation to <{}>".format(item.english_name))
        if sheet.LookupParameter(para_name).IsReadOnly:
            print ("The translation parameter for {} is read-only.".format(output.linkify(sheet.Id, title = item.english_name)))
            failed_count += 1
            continue
        sheet.LookupParameter(para_name).Set(normalized)
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

        # Language selector. Each language ships with an authority-backed AEC
        # sample dictionary in get_sample_translation_dict_for_language() --
        # see that function for source citations per language.
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
            ("Hebrew", "he"),
            ("Persian (Farsi)", "fa"),
            ("Turkish", "tr"),
            ("Hindi", "hi"),
            ("Marathi", "mr"),
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

        if element is None:
            REVIT_FORMS.notification(main_text = "Nothing to validate against.",
                                                    sub_text = "This model has no {}. Add at least one before running the translator.".format(self.mode.lower()))
            return False

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



        self.revit_update_event_handler.kwargs = self.data_grid.ItemsSource, para_name, self.target_language_code
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
            u"Follow the target country's authoritative AEC standard where one exists: "
            u"GB/T 50001 (China), JIS A 0150 + AIJ (Japan), KS F 1501 + KIA (Korea), "
            u"CTE Codigo Tecnico de la Edificacion (Spain), NF DTU + CSTB (France), UNI 7559 (Italy), "
            u"DIN 1356-1 + DIN 824 (Germany), ABNT NBR 6492 + RGEU (Portugal/Brazil), "
            u"Saudi Building Code SBC + Aramco SAES-A-202 (Arabic/Modern Standard Arabic, universal across Gulf/Levant/Egypt -- no dialect variants on CDs), "
            u"Israel Architects Association de-facto convention + Technion/Bezalel pedagogy (Hebrew), "
            u"Iran National Building Regulations + IRSA (Persian/Farsi), "
            u"TSE TS 88 + TS EN ISO 7519 + Mimarlar Odasi (Turkish), "
            u"CSTT Commission for Scientific and Technical Terminology + BIS NBC 2016 + CPWD (Hindi), "
            u"Maharashtra Bhasha Vibhag Sthapatya Glossary (Marathi). "
            u"For Arabic/Hebrew/Persian: keep sheet numbers in Latin numerals (A-101 stays A-101). "
            u"For Persian: return Western digits (0-9), NOT Eastern Arabic-Indic digits (۰-۹)."
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

        # Auto-retry with batch splitting: smaller batches both work around
        # transient 5xx / payload-size limits AND improve accuracy because the
        # LLM tracks fewer items at once (less likely to drop or merge entries).
        # Recursion bottoms out at single-item batches.
        # Circuit breaker: if the proxy is hard down (every batch 500s), stop
        # after CONSECUTIVE_5XX_LIMIT failures with zero success instead of
        # grinding through every single-item retry.
        self._consecutive_5xx = 0
        self._429_retries = 0
        self._any_success = False
        self._circuit_open = False
        merged = self._translate_with_split(session_token, system_prompt, new_prompt)
        if merged is None:
            return None
        if self._circuit_open:
            REVIT_FORMS.notification(
                main_text="EnneadTab AI server appears to be down.",
                sub_text="Repeated 5xx errors -- the proxy at enneadtab.com/api/ai/desktop-chat is returning errors for every request, including single-item batches. This is a server-side problem, not a payload issue. Try again in a few minutes; if it persists, check Vercel logs for the EnneadTabHome project."
            )

        SOUND.play_sound("sound_effect_popup_msg3.wav")
        self.debug_textbox.Text = "Translation finished. {} items translated.".format(len(merged))
        return merged

    # Circuit breaker threshold: how many consecutive 5xx errors with zero
    # successful responses before we conclude the server is down and stop
    # wasting requests.
    CONSECUTIVE_5XX_LIMIT = 3

    def _translate_with_split(self, session_token, system_prompt, items, depth=0):
        """Try translating `items` as one batch. On 5xx / parse failure, split
        in half and recurse. On 429, wait briefly and retry once. On 401,
        return None (auth flow handles it). Returns merged {english: trans} dict
        across all sub-batches, or None on hard auth failure."""
        if not items:
            return {}

        # Circuit breaker: stop wasting requests if proxy is hard-down.
        if self._circuit_open:
            print("Circuit open -- skipping batch of {}".format(len(items)))
            return {}

        indent = u"  " * depth
        batch_size = len(items)
        self.debug_textbox.Text = "{}Translating batch of {}...".format(indent, batch_size)

        user_message = json.dumps(items, ensure_ascii=True)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        try:
            ai_response = AI.chat_with_token(session_token, messages, temperature=0.3, json_mode=True)
        except AI.AIRequestError as e:
            return self._handle_api_error(e, session_token, system_prompt, items, depth)

        # Success path: reset 5xx + 429 counters, mark we got at least one response.
        self._consecutive_5xx = 0
        self._429_retries = 0
        self._any_success = True

        try:
            data = json.loads(ai_response)
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object, got {}".format(type(data)))
        except Exception as e:
            print("{}Parse fail at batch={}: {}".format(indent, batch_size, e))
            return self._split_and_retry(session_token, system_prompt, items, depth, reason="parse")

        # Coverage check: LLM may silently drop keys on large batches.
        # Re-translate only the missing items in a sub-batch (preserves accuracy
        # by retrying with same prompt + context, no fabrication).
        missing = [k for k in items if k not in data]
        if missing and batch_size > 1:
            print("{}Coverage gap: {}/{} missing, retrying just those".format(indent, len(missing), batch_size))
            patch = self._translate_with_split(session_token, system_prompt, missing, depth + 1)
            if patch:
                data.update(patch)

        return data

    def _handle_api_error(self, exc, session_token, system_prompt, items, depth):
        error_msg = str(exc)
        status = getattr(exc, "status_code", None)
        indent = u"  " * depth
        print("{}API error (status={}, batch={}): {}".format(indent, status, len(items), error_msg))

        if status == 401:
            AUTH.clear_token()
            self.debug_textbox.Text = "Token expired. Please try translating again."
            return None

        # 429 = rate limit. Exponential backoff with bounded retry count.
        # Languages with heavier tokens (Hebrew, Arabic, CJK during long
        # generations) can trip Gemini's per-second TPM sub-limit even on
        # paid Tier 3 -- a sustained burst exceeds the rolling per-second
        # window. Wait + retry handles it; if still throttled after 3
        # attempts at this batch size, fall through to split (smaller
        # batch = lower per-second token rate).
        if status == 429:
            self._429_retries = getattr(self, "_429_retries", 0) + 1
            if self._429_retries <= 3:
                wait_s = 5 * (2 ** (self._429_retries - 1))  # 5, 10, 20 s
                self.debug_textbox.Text = "{}Rate-limited (attempt {}/3), waiting {}s...".format(
                    indent, self._429_retries, wait_s)
                print("{}429 backoff: attempt {}/3, sleeping {}s".format(indent, self._429_retries, wait_s))
                time.sleep(wait_s)
                return self._translate_with_split(session_token, system_prompt, items, depth + 1)
            # Exhausted 429 retries at this size -- reset counter and split.
            self._429_retries = 0
            print("{}429 exhausted at batch={}, splitting to reduce token rate".format(indent, len(items)))
            return self._split_and_retry(session_token, system_prompt, items, depth, reason="429-exhausted")

        # Treat as 5xx-equivalent: status is None (transport failure / unparsed
        # WebException response), or 500-599. Track for circuit breaker.
        is_server_error = (status is None) or (500 <= (status or 0) < 600)
        if is_server_error:
            self._consecutive_5xx += 1
            if self._consecutive_5xx >= self.CONSECUTIVE_5XX_LIMIT and not self._any_success:
                self._circuit_open = True
                self.debug_textbox.Text = "Server appears down. Stopping after {} consecutive 5xx with no success.".format(self._consecutive_5xx)
                print("CIRCUIT OPEN: {} consecutive 5xx with zero successes -- aborting further retries".format(self._consecutive_5xx))
                return {}

        # 5xx / network: split batch in half and recurse. Single-item batches
        # that still fail get marked as missing (caller's coverage logic handles).
        return self._split_and_retry(session_token, system_prompt, items, depth, reason="status={}".format(status))

    def _split_and_retry(self, session_token, system_prompt, items, depth, reason):
        indent = u"  " * depth
        if len(items) <= 1:
            print("{}Single-item batch failed ({}); marking as untranslated: {}".format(indent, reason, items))
            return {}

        mid = len(items) // 2
        left, right = items[:mid], items[mid:]
        self.debug_textbox.Text = "{}Splitting batch of {} into {}+{} (reason: {})".format(
            indent, len(items), len(left), len(right), reason)
        print("{}Splitting {} -> {} + {} (reason: {})".format(indent, len(items), len(left), len(right), reason))

        # Small backoff before retrying. Helps when failures are caused by
        # upstream rate limits (Gemini 15 RPM on API-key auth) rather than
        # payload issues -- spacing requests gives the quota window time to
        # tick. Capped so worst case stays bounded for big batches.
        backoff_s = min(1.0 + 0.5 * depth, 4.0)
        time.sleep(backoff_s)

        merged = {}
        left_result = self._translate_with_split(session_token, system_prompt, left, depth + 1)
        if left_result is None:
            return None  # hard auth failure -- abort whole tree
        merged.update(left_result)

        # Brief pause between sibling sub-batches too -- prevents back-to-back
        # firing on rate-limited proxies.
        time.sleep(0.5)

        right_result = self._translate_with_split(session_token, system_prompt, right, depth + 1)
        if right_result is None:
            return None
        merged.update(right_result)
        return merged

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
        """Get authority-backed AEC sample translations for the selected language.

        Every language ships with a curated dictionary derived from a national
        standards body, professional architects' association, or government
        glossary -- not generic LLM defaults. Sources cited per branch. ASCII-
        only Unicode escapes per IronPython 2.7 source-encoding requirement.
        """
        if lang_code == "zh-CN":
            return self.get_sample_translation_dict()
        if lang_code == "zh-TW":
            # Source: Taiwan Architectural Drawing Standards (CNS),
            # Architects Association of R.O.C. de-facto practice
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
            # Source: JIS A 0150 (architectural drawing standards), AIJ
            # (Architectural Institute of Japan) conventions
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
            # Source: KS F 1501 (architectural drawing), KIA (Korean Institute
            # of Architects). Verified by DaYeon Kim (Korean architect) 2026-04-08
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
        if lang_code == "es":
            # Source: Codigo Tecnico de la Edificacion (CTE) Spain, MINISTERIO
            # DE TRANSPORTES Y MOVILIDAD SOSTENIBLE
            samples = dict()
            samples["SITE PLAN"] = u"Plano de Situaci\xf3n"
            samples["FLOOR PLAN"] = u"Planta"
            samples["ROOF PLAN"] = u"Planta de Cubiertas"
            samples["REFLECTED CEILING PLAN"] = u"Plano de Techos Reflejado"
            samples["BUILDING ELEVATIONS"] = u"Alzados"
            samples["BUILDING SECTIONS"] = u"Secciones"
            samples["COVER SHEET"] = u"Portada"
            samples["DRAWING LIST"] = u"\xcdndice de Planos"
            samples["DETAIL"] = u"Detalle"
            samples["GROUND FLOOR"] = u"Planta Baja"
            samples["BASEMENT"] = u"S\xf3tano"
            samples["STAIR"] = u"Escalera"
            return samples
        if lang_code == "fr":
            # Source: NF DTU (Documents Techniques Unifies), CSTB (Centre
            # Scientifique et Technique du Batiment), Ordre des Architectes
            samples = dict()
            samples["SITE PLAN"] = u"Plan de Situation"
            samples["FLOOR PLAN"] = u"Plan d'\xc9tage"
            samples["ROOF PLAN"] = u"Plan de Toiture"
            samples["REFLECTED CEILING PLAN"] = u"Plan de Plafond R\xe9fl\xe9chi"
            samples["BUILDING ELEVATIONS"] = u"\xc9l\xe9vations"
            samples["BUILDING SECTIONS"] = u"Coupes"
            samples["COVER SHEET"] = u"Page de Garde"
            samples["DRAWING LIST"] = u"Liste des Plans"
            samples["DETAIL"] = u"D\xe9tail"
            samples["GROUND FLOOR"] = u"Rez-de-Chauss\xe9e"
            samples["BASEMENT"] = u"Sous-sol"
            samples["STAIR"] = u"Escalier"
            return samples
        if lang_code == "it":
            # Source: UNI 7559 (architectural drawing terminology),
            # Consiglio Nazionale degli Architetti Pianificatori (CNAPPC)
            samples = dict()
            samples["SITE PLAN"] = u"Planimetria Generale"
            samples["FLOOR PLAN"] = u"Pianta"
            samples["ROOF PLAN"] = u"Pianta delle Coperture"
            samples["REFLECTED CEILING PLAN"] = u"Pianta del Controsoffitto"
            samples["BUILDING ELEVATIONS"] = u"Prospetti"
            samples["BUILDING SECTIONS"] = u"Sezioni"
            samples["COVER SHEET"] = u"Frontespizio"
            samples["DRAWING LIST"] = u"Elenco Tavole"
            samples["DETAIL"] = u"Dettaglio"
            samples["GROUND FLOOR"] = u"Piano Terra"
            samples["BASEMENT"] = u"Piano Interrato"
            samples["STAIR"] = u"Scala"
            return samples
        if lang_code == "de":
            # Source: DIN 1356-1 (Bauzeichnungen / building drawings),
            # DIN 824 (sheet sizes), Bundesarchitektenkammer (BAK)
            samples = dict()
            samples["SITE PLAN"] = u"Lageplan"
            samples["FLOOR PLAN"] = u"Grundriss"
            samples["ROOF PLAN"] = u"Dachaufsicht"
            samples["REFLECTED CEILING PLAN"] = u"Deckenspiegel"
            samples["BUILDING ELEVATIONS"] = u"Ansichten"
            samples["BUILDING SECTIONS"] = u"Schnitte"
            samples["COVER SHEET"] = u"Deckblatt"
            samples["DRAWING LIST"] = u"Planliste"
            samples["DETAIL"] = u"Detail"
            samples["GROUND FLOOR"] = u"Erdgeschoss"
            samples["BASEMENT"] = u"Untergeschoss"
            samples["STAIR"] = u"Treppe"
            return samples
        if lang_code == "pt":
            # Source: ABNT NBR 6492 (Brazilian arch. drawing standard),
            # RGEU Portugal (Regulamento Geral das Edificacoes Urbanas)
            samples = dict()
            samples["SITE PLAN"] = u"Planta de Situa\xe7\xe3o"
            samples["FLOOR PLAN"] = u"Planta Baixa"
            samples["ROOF PLAN"] = u"Planta de Cobertura"
            samples["REFLECTED CEILING PLAN"] = u"Planta de Forro"
            samples["BUILDING ELEVATIONS"] = u"Eleva\xe7\xf5es"
            samples["BUILDING SECTIONS"] = u"Cortes"
            samples["COVER SHEET"] = u"Folha de Rosto"
            samples["DRAWING LIST"] = u"Lista de Pranchas"
            samples["DETAIL"] = u"Detalhe"
            samples["GROUND FLOOR"] = u"T\xe9rreo"
            samples["STAIR"] = u"Escada"
            return samples
        if lang_code == "ar":
            # Source: Saudi Building Code (SBC), Saudi Aramco SAES-A-202
            # (Engineering Drawing Preparation), Dubai Municipality bilingual
            # standards. Modern Standard Arabic (MSA) is universal across all
            # Arab markets -- no per-country variant needed.
            samples = dict()
            samples["SITE PLAN"] = u"\u0645\u062e\u0637\u0637 \u0627\u0644\u0645\u0648\u0642\u0639"
            samples["FLOOR PLAN"] = u"\u0645\u0633\u0642\u0637 \u0623\u0641\u0642\u064a"
            samples["ROOF PLAN"] = u"\u0645\u0633\u0642\u0637 \u0627\u0644\u0633\u0637\u062d"
            samples["REFLECTED CEILING PLAN"] = u"\u0645\u0633\u0642\u0637 \u0627\u0644\u0633\u0642\u0641 \u0627\u0644\u0645\u0639\u0643\u0648\u0633"
            samples["BUILDING ELEVATIONS"] = u"\u0648\u0627\u062c\u0647\u0627\u062a"
            samples["BUILDING SECTIONS"] = u"\u0645\u0642\u0627\u0637\u0639"
            samples["COVER SHEET"] = u"\u0635\u0641\u062d\u0629 \u0627\u0644\u063a\u0644\u0627\u0641"
            samples["DRAWING LIST"] = u"\u0642\u0627\u0626\u0645\u0629 \u0627\u0644\u0631\u0633\u0648\u0645\u0627\u062a"
            samples["DETAIL"] = u"\u062a\u0641\u0635\u064a\u0644"
            samples["STAIR"] = u"\u062f\u0631\u062c"
            samples["SCHEDULE"] = u"\u062c\u062f\u0648\u0644"
            samples["NORTH ARROW"] = u"\u0633\u0647\u0645 \u0627\u0644\u0634\u0645\u0627\u0644"
            return samples
        if lang_code == "he":
            # Source: Israel Architects Association (architecture.org.il)
            # de-facto convention (no SII drawing-terminology standard exists);
            # Technion / Bezalel pedagogy
            samples = dict()
            samples["SITE PLAN"] = u"\u05ea\u05db\u05e0\u05d9\u05ea \u05e4\u05d9\u05ea\u05d5\u05d7"
            samples["FLOOR PLAN"] = u"\u05ea\u05db\u05e0\u05d9\u05ea \u05e7\u05d5\u05de\u05d4"
            samples["ROOF PLAN"] = u"\u05ea\u05db\u05e0\u05d9\u05ea \u05d2\u05d2"
            samples["REFLECTED CEILING PLAN"] = u"\u05ea\u05db\u05e0\u05d9\u05ea \u05ea\u05e7\u05e8\u05d4 \u05de\u05e9\u05ea\u05e7\u05e4\u05ea"
            samples["BUILDING ELEVATIONS"] = u"\u05d7\u05d6\u05d9\u05ea\u05d5\u05ea"
            samples["BUILDING SECTIONS"] = u"\u05d7\u05ea\u05db\u05d9\u05dd"
            samples["COVER SHEET"] = u"\u05d3\u05e3 \u05e9\u05e2\u05e8"
            samples["DRAWING LIST"] = u"\u05e8\u05e9\u05d9\u05de\u05ea \u05ea\u05db\u05e0\u05d9\u05d5\u05ea"
            samples["DETAIL"] = u"\u05e4\u05e8\u05d8"
            samples["STAIR"] = u"\u05de\u05d3\u05e8\u05d2\u05d5\u05ea"
            samples["SCHEDULE"] = u"\u05e8\u05e9\u05d9\u05de\u05d4"
            return samples
        if lang_code == "fa":
            # Source: Iran National Building Regulations (Moqararat-e Melli-e
            # Sakhteman), 22-volume code from Ministry of Roads & Urban
            # Development; IRSA pedagogy (Tehran/Isfahan practice).
            # NOTE: no government bilingual EN-FA glossary exists.
            samples = dict()
            samples["SITE PLAN"] = u"\u067e\u0644\u0627\u0646 \u0645\u0648\u0642\u0639\u06cc\u062a"
            samples["FLOOR PLAN"] = u"\u067e\u0644\u0627\u0646 \u0637\u0628\u0642\u0647"
            samples["ROOF PLAN"] = u"\u067e\u0644\u0627\u0646 \u0628\u0627\u0645"
            samples["REFLECTED CEILING PLAN"] = u"\u067e\u0644\u0627\u0646 \u0633\u0642\u0641 \u06a9\u0627\u0630\u0628"
            samples["BUILDING ELEVATIONS"] = u"\u0646\u0645\u0627"
            samples["BUILDING SECTIONS"] = u"\u0645\u0642\u0637\u0639"
            samples["COVER SHEET"] = u"\u0635\u0641\u062d\u0647 \u062c\u0644\u062f"
            samples["DRAWING LIST"] = u"\u0641\u0647\u0631\u0633\u062a \u0646\u0642\u0634\u0647 \u0647\u0627"
            samples["DETAIL"] = u"\u062c\u0632\u0626\u06cc\u0627\u062a"
            samples["GROUND FLOOR"] = u"\u0647\u0645\u06a9\u0641"
            samples["SCHEDULE"] = u"\u062c\u062f\u0648\u0644"
            return samples
        if lang_code == "tr":
            # Source: TSE TS 88 (adopts ISO 128), TS EN ISO 7519 (construction
            # drawing principles), TS 2120 (dimensioning); Mimarlar Odasi
            # (Chamber of Architects) sheet-naming convention
            samples = dict()
            samples["SITE PLAN"] = u"Vaziyet Plan\u0131"
            samples["FLOOR PLAN"] = u"Kat Plan\u0131"
            samples["ROOF PLAN"] = u"\xc7at\u0131 Plan\u0131"
            samples["REFLECTED CEILING PLAN"] = u"Tavan Plan\u0131"
            samples["BUILDING ELEVATIONS"] = u"Cephe G\xf6r\xfcn\xfc\u015fleri"
            samples["BUILDING SECTIONS"] = u"Bina Kesitleri"
            samples["COVER SHEET"] = u"Kapak Sayfas\u0131"
            samples["DRAWING LIST"] = u"\xc7izim Listesi"
            samples["DETAIL"] = u"Detay"
            samples["GROUND FLOOR PLAN"] = u"Zemin Kat Plan\u0131"
            samples["BASEMENT PLAN"] = u"Bodrum Kat Plan\u0131"
            samples["STAIR"] = u"Merdiven"
            return samples
        if lang_code == "hi":
            # Source: CSTT (Commission for Scientific and Technical Terminology),
            # Ministry of Education Govt. of India -- Architecture and Civil
            # Engineering English-Hindi glossaries. Backed by BIS NBC 2016 and
            # CPWD Works Manual for general AEC vocabulary.
            samples = dict()
            samples["SITE PLAN"] = u"\u0938\u094d\u0925\u0932 \u092f\u094b\u091c\u0928\u093e"
            samples["FLOOR PLAN"] = u"\u0924\u0932 \u092f\u094b\u091c\u0928\u093e"
            samples["ROOF PLAN"] = u"\u091b\u0924 \u092f\u094b\u091c\u0928\u093e"
            samples["REFLECTED CEILING PLAN"] = u"\u091b\u0924 \u092a\u094d\u0930\u0924\u093f\u092c\u093f\u092e\u094d\u092c \u092f\u094b\u091c\u0928\u093e"
            samples["BUILDING ELEVATIONS"] = u"\u092d\u0935\u0928 \u0909\u0928\u094d\u0928\u092f\u0928"
            samples["BUILDING SECTIONS"] = u"\u092d\u0935\u0928 \u0905\u0928\u0941\u092d\u093e\u0917"
            samples["COVER SHEET"] = u"\u0906\u0935\u0930\u0923 \u092a\u0943\u0937\u094d\u0920"
            samples["DRAWING LIST"] = u"\u0930\u0947\u0916\u093e\u0902\u0915\u0928 \u0938\u0942\u091a\u0940"
            samples["DETAIL"] = u"\u0935\u093f\u0935\u0930\u0923"
            samples["FOUNDATION PLAN"] = u"\u0928\u0940\u0902\u0935 \u092f\u094b\u091c\u0928\u093e"
            samples["SCHEDULE"] = u"\u0905\u0928\u0941\u0938\u0942\u091a\u0940"
            samples["SCALE"] = u"\u092e\u093e\u092a\u0915"
            return samples
        if lang_code == "mr":
            # Source: Maharashtra Govt. Marathi Bhasha Vibhag --
            # "Sthapatya Abhiyantriki Paribhasha Kosh" (Architecture & Civil
            # Engineering Glossary), shabdakosh.marathi.gov.in. Distinct from
            # CSTT; state-level authority.
            samples = dict()
            samples["SITE PLAN"] = u"\u0938\u094d\u0925\u0933 \u092f\u094b\u091c\u0928\u093e"
            samples["FLOOR PLAN"] = u"\u0924\u0933 \u092f\u094b\u091c\u0928\u093e"
            samples["ROOF PLAN"] = u"\u091b\u0924 \u092f\u094b\u091c\u0928\u093e"
            samples["BUILDING ELEVATIONS"] = u"\u0907\u092e\u093e\u0930\u0924 \u0909\u0928\u094d\u0928\u092f\u0928"
            samples["BUILDING SECTIONS"] = u"\u0907\u092e\u093e\u0930\u0924 \u091b\u0947\u0926\u0915"
            samples["COVER SHEET"] = u"\u0906\u0935\u0930\u0923 \u092a\u0943\u0937\u094d\u0920"
            samples["DETAIL"] = u"\u0924\u092a\u0936\u0940\u0932"
            samples["DRAWING LIST"] = u"\u0930\u0947\u0916\u093e\u0902\u0915\u0928 \u092f\u093e\u0926\u0940"
            samples["FOUNDATION PLAN"] = u"\u092a\u093e\u092f\u093e \u092f\u094b\u091c\u0928\u093e"
            return samples
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


