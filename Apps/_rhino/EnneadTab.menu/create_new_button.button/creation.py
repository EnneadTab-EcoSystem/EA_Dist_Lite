import os



"""
this has the core function that is shared between Rhino version and IDE version
"""


TEMPLATE = '''#!/usr/bin/python
# -*- coding: utf-8 -*-

__title__ = "{0}"
__doc__ = """{1}"""


from EnneadTab import ERROR_HANDLE, LOG

@LOG.log(__file__, __title__)
@ERROR_HANDLE.try_catch_error()
def {2}():
    {3}


if __name__ == "__main__":
    {2}()
'''

# Seed doc for a freshly generated button. Must satisfy the doc-style gate
# (tools/check_doc_style.py): explicit __doc__ assignment, verb-first first
# line under 90 chars, no status markers. Spec:
# .claude/skills/enneadtab-doc-writing/SKILL.md
DEFAULT_DOC = """Describe here what the user gets when they run {0}.

Rewrite this before publishing. The first line is a verb-first outcome
sentence under 90 characters, written for an architect, not a developer.
See .claude/skills/enneadtab-doc-writing/SKILL.md for the full spec."""

SAMPLE_PRINT_STATMENT ='print ("Func <{}> not implemented yet. Doc says: {}".format(__title__, __doc__))'

def make_button(tab_folder, button_name, is_left_click = True):
    print (tab_folder)
    print (button_name)
    clicker = "left" if is_left_click else "right"
    better_alias = button_name.replace("_", " ").title().replace(" ", "")
    doc = DEFAULT_DOC.format(better_alias)
    script = TEMPLATE.format(better_alias, doc, button_name, SAMPLE_PRINT_STATMENT)
    print (script)

   

    button_folder = "{}\\{}.button".format(tab_folder, button_name.replace(" ", "_"))
    if not os.path.exists(button_folder):
        os.makedirs(button_folder)

    for file in os.listdir(button_folder):
        if file.endswith(".py") and clicker in file:
            print ("File with this click method exist.....check the folder.")
            return
            
    script_file = "{}\\{}_{}.py".format(button_folder, button_name, clicker )


    with open(script_file, "w") as f:
        f.write(script)
    
    os.startfile(script_file)






 

    