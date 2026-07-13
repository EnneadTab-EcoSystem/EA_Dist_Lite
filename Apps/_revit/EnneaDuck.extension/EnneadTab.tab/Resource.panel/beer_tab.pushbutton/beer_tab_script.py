#!/usr/bin/python
# -*- coding: utf-8 -*-



__doc__ = """Open a guide to the nearest places to get a beer.

A one-click break button for the end of a long modeling session. Opens a
neighborhood beer guide in your browser. Nothing in the model is touched."""
__title__ = "Beer\nTab"
__context__ = "zero-doc"


import proDUCKtion # pyright: ignore

from EnneadTab import ERROR_HANDLE, LOG
import webbrowser

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def beer_tab():
    webbrowser.open("https://beerswithmandy.com/beer-everything-blog/where-to-get-a-beer-in-nyc-financial-district-fidi")


################## main code below #####################


if __name__ == "__main__":
    beer_tab()
