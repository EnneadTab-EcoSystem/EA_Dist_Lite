#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Launch SparcHealth orchestrator to perform health checks on all Sparc project models. The orchestrator will open each model sequentially, collect health metrics, and save results to the OneDrive Dump folder."""
__title__ = "SparcHealth"

import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, LOG
import os
import subprocess

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def launch_sparc_health():
    """Launch the SparcHealth orchestrator"""
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the batch file
    batch_file = os.path.join(script_dir, "run_SparcHealth.bat")
    
    if not os.path.exists(batch_file):
        print("ERROR: Batch file not found: {}".format(batch_file))
        return
    
    # Launch the batch file in a new console window
    print("Launching SparcHealth orchestrator...")
    print("Batch file: {}".format(batch_file))
    
    try:
        # Use START to open in a new window that stays open
        cmd = 'start "SparcHealth Orchestrator" cmd /k "{}"'.format(batch_file)
        subprocess.Popen(cmd, shell=True)
        
        print("SparcHealth orchestrator launched successfully!")
        print("Monitor the orchestrator window for progress.")
    except Exception as e:
        print("ERROR launching orchestrator: {}".format(e))
        raise


################## main code below #####################
if __name__ == "__main__":
    launch_sparc_health()

