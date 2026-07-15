from Autodesk.Revit import UI  # pyright: ignore
# pyRevit hook engines do not inherit the .lib search path that button scripts get,
# so put KingDuck.lib on sys.path before importing proDUCKtion (the EnneadTab bootstrap).
import os, sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "KingDuck.lib")))
import proDUCKtion  # pyright: ignore
proDUCKtion.validify()
from EnneadTab import ERROR_HANDLE, SOUND

def play_closing_sound():
    file = "sound_effect_mario_game_over.wav"
    SOUND.play_sound(file)

@ERROR_HANDLE.try_catch_error(is_silent=True)
def main():
    # general_annoucement()

    play_closing_sound()

if __name__ == "__main__":
    main()