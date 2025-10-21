#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Post-Export Logic for NYU HQ Auto Export
Handles email notifications and post-export tasks
"""

import os
from datetime import datetime
from EnneadTab import EMAIL

# =============================================================================
# GLOBAL CONSTANTS - EMAIL CONFIGURATION
# =============================================================================

# Email recipients
EMAIL_RECIPIENTS = [
    "szhang@ennead.com",
    "DaYeon.Kim@ennead.com"
]

# Email subject template
EMAIL_SUBJECT = "NYU HQ Auto Export Completed - {date}"

# Email body template
EMAIL_BODY_TEMPLATE = """
NYU HQ Auto Export Report
========================

Export Date: {date}
Project: {project_name}
PIM Number: {pim_number}

Export Summary:
- PDF Files: {pdf_count} files
- DWG Files: {dwg_count} files  
- JPG Files: {jpg_count} files

Export Location:
{export_path}

Files Exported:
{pdf_files}
{dwg_files}
{jpg_files}

This is an automated export from the NYU HQ Revit model.
All files have been exported with the PIM number prefix for proper project identification.

Best regards,
EnneadTab Auto Export System
"""


def send_export_email(export_results, pim_number, project_name, heartbeat_callback=None):
    """Send email notification after export completion
    
    Args:
        export_results: Dictionary with export results from run_all_exports
        pim_number: PIM number from project info
        project_name: Name of the project
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    def log(message, is_error=False):
        """Helper to log messages"""
        print(message)
        if heartbeat_callback:
            heartbeat_callback("EMAIL", message, is_error=is_error)
    
    try:
        log("Preparing email notification...")
        
        # Prepare email content
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        subject = EMAIL_SUBJECT.format(date=current_date)
        
        # Format file lists
        pdf_list = "\n".join(["- " + os.path.basename(f) for f in export_results["pdf_files"]])
        dwg_list = "\n".join(["- " + os.path.basename(f) for f in export_results["dwg_files"]])
        jpg_list = "\n".join(["- " + os.path.basename(f) for f in export_results["jpg_files"]])
        
        # Create email body
        body = EMAIL_BODY_TEMPLATE.format(
            date=current_date,
            project_name=project_name,
            pim_number=pim_number or "Not found",
            pdf_count=len(export_results["pdf_files"]),
            dwg_count=len(export_results["dwg_files"]),
            jpg_count=len(export_results["jpg_files"]),
            export_path=export_results["folder_paths"]["weekly"],
            pdf_files=pdf_list or "No PDF files exported",
            dwg_files=dwg_list or "No DWG files exported", 
            jpg_files=jpg_list or "No JPG files exported"
        )
        
        log("Email content prepared")
        log("Subject: {}".format(subject))
        log("Recipients: {}".format(", ".join(EMAIL_RECIPIENTS)))
        
        # Send email using EnneadTab email service
        try:
            log("Sending email using EnneadTab email service...")
            EMAIL.email(
                receiver_email_list=EMAIL_RECIPIENTS,
                body=body,
                subject=subject,
                attachment_list=[]
            )
            log("Email sent successfully to: {}".format(", ".join(EMAIL_RECIPIENTS)))
            return True
        except Exception as email_error:
            log("Email sending failed: {}".format(str(email_error)), is_error=True)
            log("Email body preview:")
            print("="*50)
            print(body)
            print("="*50)
            return False
        
    except Exception as e:
        log("Email sending error: {}".format(str(e)), is_error=True)
        return False


def run_post_export_tasks(export_results, pim_number, project_name, heartbeat_callback=None):
    """Run all post-export tasks (email notifications, etc.)
    
    Args:
        export_results: Dictionary with export results from run_all_exports
        pim_number: PIM number from project info
        project_name: Name of the project
        heartbeat_callback: Optional function to call for logging progress
    
    Returns:
        dict: Dictionary with post-export task results
    """
    def log(message, is_error=False):
        """Helper to log messages"""
        print(message)
        if heartbeat_callback:
            heartbeat_callback("POST_EXPORT", message, is_error=is_error)
    
    try:
        log("Starting post-export tasks...")
        
        # Check if there are any successful exports
        total_exports = (len(export_results["pdf_files"]) + 
                        len(export_results["dwg_files"]) + 
                        len(export_results["jpg_files"]))
        
        if total_exports == 0:
            log("No files exported - skipping email notification")
            return {
                "email_sent": False,
                "tasks_completed": ["no_export_skip"],
                "reason": "No files exported"
            }
        
        log("Found {} total files exported - proceeding with email notification".format(total_exports))
        
        # Send email notification
        email_success = send_export_email(export_results, pim_number, project_name, heartbeat_callback)
        
        log("Post-export tasks completed")
        
        return {
            "email_sent": email_success,
            "tasks_completed": ["email_notification"]
        }
        
    except Exception as e:
        log("Post-export error: {}".format(str(e)), is_error=True)
        return {
            "email_sent": False,
            "tasks_completed": [],
            "error": str(e)
        }
