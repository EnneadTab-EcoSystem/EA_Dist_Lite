#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "AI-powered quality control assistant that transforms complex model data into actionable insights. This tool generates comprehensive QAQC reports for your current document and features a natural language interface powered by EnneaDuck AI, allowing you to interrogate the results through simple conversation. Perfect for project milestones, coordination reviews, or when preparing deliverables that require rigorous quality verification."
__title__ = "QAQC\nReporter"
__is_popular__ = True

import System # pyright: ignore
import os
import time
import random

from pyrevit import script
from pyrevit import forms
from pyrevit.forms import WPFWindow # pyright: ignore
from Autodesk.Revit import DB # pyright: ignore

import proDUCKtion # pyright: ignore
proDUCKtion.validify()
from EnneadTab.REVIT import REVIT_FORMS
from EnneadTab import DATA_FILE, SOUND, TIME, ERROR_HANDLE, FOLDER, IMAGE, LOG, JOKE, AUTH, AI

uidoc = __revit__.ActiveUIDocument
doc = __revit__.ActiveUIDocument.Document # pyright: ignore
__persistentengine__ = True










# A simple WPF form used to call the ExternalEvent
class AI_Report_modelessForm(WPFWindow):
    """
    Simple modeless form sample
    """
    def initiate_form(self):
        sample = ["What are the critical issues?",
                    "Give a quick overall summery of the report",
                    "Who has the most critical warnings?"]
        self.tbox_input.Text = random.choice(sample)



    @ERROR_HANDLE.try_catch_error()
    def __init__(self):
        xaml_file_name = "QAQC_Reporter_ModelessForm.xaml"
        WPFWindow.__init__(self, xaml_file_name)

        self.title_text.Text = "EnneaDuck: Chat With Document"

        self.sub_text.Text = "Use EnneaDuck AI to answer all kinds of questions in current document or from existing QAQC report."


        self.Title = "QAQC Reporter"
        #self.Width = 800
        self.Height = 1000
        logo_file = IMAGE.get_image_path_by_name("logo_vertical_light.png")
        self.set_image_source(self.logo_img, logo_file)
        self.set_image_source(self.pop_warning_img, "pop_warning.png")
    
        self.initiate_form()
        self.get_previous_conversation()
        self.session_name = "QAQC_SESSION_{}".format(TIME.get_formatted_current_time())
        self.Show()


    @property
    def log_file(self):
        return "QAQC_REPORT_LOG"

   
    def get_previous_conversation(self):
        log_file_path = FOLDER.get_local_dump_folder_file(self.log_file)
        if os.path.exists(log_file_path):
            record = DATA_FILE.get_data(log_file_path)
            self.tbox_conversation.Text = record["conversation_history"]
        else:
            self.tbox_conversation.Text = ""

    @ERROR_HANDLE.try_catch_error()
    def ask_Click(self, sender, e):
        # 2026-04-08: Migrated from OpenAI EXE to EnneadTab AI proxy (Gemini backend)
        query = self.tbox_input.Text
        if not query or not query.strip():
            self.debug_textbox.Text = "Please enter a question."
            return

        # Build context from report or PDF
        if self.radio_bt_is_reading_pdf.IsChecked:
            if not hasattr(self, "pdf"):
                self.debug_textbox.Text = "You need to pick pdf first...."
                return
            context_text = "User has a PDF QAQC report at: {}".format(self.pdf)
        else:
            if not hasattr(self, "report"):
                self.debug_textbox.Text = "You need to run the report first...."
                return
            context_text = self.report

        # Get auth token (lazy browser OAuth)
        session_token = AUTH.get_token()
        if not session_token:
            if not AUTH.is_auth_in_progress():
                AUTH.request_auth()
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
                return

        self.debug_textbox.Text = JOKE.random_loading_message()

        system_prompt = (
            "You are a QAQC expert for architectural Revit models at Ennead Architects. "
            "Analyze the following QAQC report data and answer the user's question clearly and concisely. "
            "Focus on actionable insights. If the data is insufficient, say so.\n\n"
            "QAQC Report Data:\n{}"
        ).format(context_text[:8000])

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query}
        ]

        try:
            ai_response = AI.chat_with_token(session_token, messages, temperature=0.7)
            SOUND.play_sound("sound_effect_popup_msg3.wav")
            self.tbox_conversation.Text += "\n\nQ: {}\nA: {}".format(query, ai_response)
            self.debug_textbox.Text = "Done."

        except AI.AIRequestError as e:
            if e.status_code == 401:
                AUTH.clear_token()
                self.debug_textbox.Text = "Token expired. Please try again."
                return
            self.debug_textbox.Text = "AI request failed: {}".format(str(e)[:200])
        
  

            

    @ERROR_HANDLE.try_catch_error()
    def clear_history_Click(self, sender, e):
        if FOLDER.is_file_exist_in_dump_folder(self.log_file):
            FOLDER.remove_file_from_dump_folder(self.log_file)
        self.tbox_conversation.Text = ''
        #self.conversation_SimpleEventHandler.OUT = None
        pass

    def mouse_move_event(self, sender, args):
        #print "mouse down"
        #self.debug_textbox.Text = self.simple_event_handler.OUT
        pass

    def mouse_down_main_panel(self, sender, args):
        #print "mouse down"
        sender.DragMove()


    def close_Click(self, sender, args):
        self.save_conversation()
        #print "mouse down"
        self.Close()
        #self.debug_textbox.Text = self.simple_event_handler.OUT
        pass

    def save_conversation(self):
        record = dict()
        record["conversation_history"] = self.tbox_conversation.Text
        DATA_FILE.set_data(record, self.log_file)

    @ERROR_HANDLE.try_catch_error()
    def generate_report_click(self, sender, args):
        import QAQC_runner
        self.report = QAQC_runner.QAQC(script.get_output()).get_report(pdf_file = None, save_html = self.is_saving_html.IsChecked)

        if self.report == "PREVIOUSLY CLOSED":
            REVIT_FORMS.notification(main_text = "You have closed your last report window.", sub_text = "Please restart the QAQC reporter if you want to see the report again.")
            self.Close()

    @ERROR_HANDLE.try_catch_error()
    def bt_pick_pdf_clicked(self, sender, args):
        self.pdf = forms.pick_file(file_ext='*.pdf')
        if not self.pdf:
            return
        self.pdf_display.Text = self.pdf


    @ERROR_HANDLE.try_catch_error()
    def radial_bt_source_changed(self, sender, args):
        if self.radio_bt_is_reading_pdf.IsChecked:
            self.pdf_source_panel.Visibility = System.Windows.Visibility.Visible
        else:
            self.pdf_source_panel.Visibility = System.Windows.Visibility.Collapsed


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def main():
    output = script.get_output()
    output.close_others()


    AI_Report_modelessForm()


if __name__ == "__main__":
    main()











  
        
