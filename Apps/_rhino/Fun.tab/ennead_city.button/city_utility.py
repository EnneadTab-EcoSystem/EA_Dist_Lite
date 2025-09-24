#!/usr/bin/python
# -*- coding: utf-8 -*-
import os
import sys

# Get the correct path to the lib folder
current_dir = os.path.dirname(os.path.realpath(__file__))
lib_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))), "lib")
sys.path.append(lib_path)

from EnneadTab import ENVIRONMENT, DATA_FILE, FOLDER, USER


MAIN_FOLDER = os.path.join(ENVIRONMENT.DB_FOLDER, "EnneadCity")
USER_DATA_FILE = os.path.join(MAIN_FOLDER, "city_setting")
PLOT_FILES_FOLDER = os.path.join(MAIN_FOLDER, "plots")
CITY_SOURCE_FILE = os.path.join(MAIN_FOLDER, "City_Source.3dm")
CITY_BACKGROUND_FILES = [os.path.join(MAIN_FOLDER, "City_Background_Road.3dm")]


def get_city_data():
    # Ensure the main folder exists
    if not os.path.exists(MAIN_FOLDER):
        try:
            os.makedirs(MAIN_FOLDER)
        except OSError:
            pass  # Directory already exists or permission denied
    
    if not os.path.exists(USER_DATA_FILE):
        print("Create empty user data file")
        try:
            DATA_FILE.set_data(dict(), USER_DATA_FILE)
        except Exception as e:
            print("Error creating user data file: {}".format(str(e)))
            # Fallback: create empty dict
            return dict()
    
    try:
        return DATA_FILE.get_data(USER_DATA_FILE)
    except Exception as e:
        print("Error reading user data file: {}".format(str(e)))
        # Try alternative method if get_data fails
        try:
            import json
            with open(USER_DATA_FILE, 'r') as f:
                return json.load(f)
        except:
            return dict()


def get_current_user_plot_file():

    user_name = USER.USER_NAME
    user_data = get_city_data()
    if user_name not in user_data:
        return False

    return user_data[user_name]["plot_file"]


def set_current_user_plot_file(plot_file):
    user_name = USER.USER_NAME
    user_data = get_city_data()
    # print user_data
    if user_name not in user_data.keys():
        user_data[user_name] = dict()
    user_data[user_name]["plot_file"] = plot_file
    # print plot_file
    # print user_data
    try:
        DATA_FILE.set_data(user_data, USER_DATA_FILE)
    except Exception as e:
        print("Error saving user plot file: {}".format(str(e)))


def get_all_plot_files():
    # Ensure the plots folder exists
    if not os.path.exists(PLOT_FILES_FOLDER):
        try:
            os.makedirs(PLOT_FILES_FOLDER)
        except OSError:
            pass  # Directory already exists or permission denied
        return []
    
    return [os.path.join(PLOT_FILES_FOLDER, plot_file) for plot_file in os.listdir(PLOT_FILES_FOLDER) if plot_file.endswith(".3dm")]


def get_empty_plot_files():
    used_plots = get_occupied_plot_files()
    return [plot_file for plot_file in get_all_plot_files() if plot_file not in used_plots]


def get_occupied_plot_files():
    user_data = get_city_data()
    occupied_plots = []
    for user_name in user_data:
        if "plot_file" in user_data[user_name]:
            occupied_plots.append(user_data[user_name]["plot_file"])
    return occupied_plots


def get_occupied_plot_names():
    used_plots = get_occupied_plot_files()
    return [os.path.split(x)[1].replace(".3dm", "") for x in used_plots]
