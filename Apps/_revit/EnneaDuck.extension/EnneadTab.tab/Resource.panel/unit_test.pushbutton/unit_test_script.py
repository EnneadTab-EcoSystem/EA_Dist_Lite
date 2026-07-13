#!/usr/bin/python
# -*- coding: utf-8 -*-

__doc__ = """Run a self-check on the core EnneadTab services and report anything broken.

Reach for this when EnneadTab starts behaving strangely after an update. It
exercises the shared services every other tool leans on and prints a pass or fail
for each one, which is worth pasting into a bug report."""
__title__ = "Unit Test"
__context__ = "zero-doc"


import proDUCKtion # pyright: ignore 
proDUCKtion.validify()

from EnneadTab import ERROR_HANDLE, UNIT_TEST, LOG


@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def unit_test():
    UNIT_TEST.test_core_module()



################## main code below #####################
if __name__ == "__main__":
    unit_test()







