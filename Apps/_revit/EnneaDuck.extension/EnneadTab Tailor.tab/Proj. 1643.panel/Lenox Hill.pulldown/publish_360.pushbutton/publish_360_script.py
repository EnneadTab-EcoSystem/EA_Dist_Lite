#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = "Trigger a C4R cloud publish (without links) for the Lenox Hill central model via the BIM 360 Data Management API."
__title__ = "publish_360"

from pyrevit import script #

from EnneadTab import ERROR_HANDLE, NOTIFICATION
from EnneadTab.REVIT import REVIT_ACC

try:
    import requests
except Exception:
    requests = None

# BIM 360 identifiers for Proj. 1643 Lenox Hill. These are resource ids, not secrets.
# To convert a project ID in the BIM 360 API into a project ID in the Data Management API you need to add a "b." prefix.
# For example, a project ID of c8b0c73d-3ae9 translates to a project ID of b.c8b0c73d-3ae9.
PROJECT_ID = "b.ccf84983-1c3b-4cc0-baac-73198b3364be"
ITEM_URN = "urn:adsk.wip:dm.file:hC6k4hndRWaeIVhIjvHu8w"
COMMANDS_URL = "https://developer.api.autodesk.com/data/v1/projects/{}/commands/".format(PROJECT_ID)


@ERROR_HANDLE.try_catch_error()
def publish_360():
    if requests is None:
        NOTIFICATION.messenger("requests module not available - cannot reach the Autodesk API.")
        return

    # Auth goes through the shared SECRET-backed token helper (cached 2-legged OAuth).
    # Never put client ids, client secrets, or access tokens in this file.
    access_token = REVIT_ACC.get_reusable_access_token()
    if not access_token:
        NOTIFICATION.messenger("Could not get an APS access token. Check ACC_API_KEY.secret availability.")
        return

    headers = {
        "Authorization": "Bearer {}".format(access_token),
        "Content-Type": "application/vnd.api+json"
    }
    payload = {
        "jsonapi": {
            "version": "1.0"
        },
        "data": {
            "type": "commands",
            "attributes": {
                "extension": {
                    "type": "commands:autodesk.bim360:C4RPublishWithoutLinks",
                    "version": "1.0.0"
                }
            },
            "relationships": {
                "resources": {
                    "data": [{"type": "items", "id": ITEM_URN}]
                }
            }
        }
    }
    response = requests.post(COMMANDS_URL, headers=headers, json=payload, timeout=30)

    if response.status_code in (200, 201, 202):
        NOTIFICATION.messenger("Publish command accepted for Lenox Hill.")
    else:
        NOTIFICATION.messenger("Publish command failed: HTTP {}".format(response.status_code))
    print(response.text)

################## main code below #####################


if __name__ == "__main__":
    output = script.get_output()
    output.close_others()
    publish_360()
