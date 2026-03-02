import os
import sys
import tkinter as tk

# Add current directory to path to allow importing local modules (ui, data_manager)
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from ui import TimeSheetApp
except ImportError as e:
    print(f"Error importing UI: {e}")
    sys.exit(1)

def main():
    root = tk.Tk()
    
    # Set geometry and position if needed, or let it autosize
    # root.geometry("800x600")
    
    app = TimeSheetApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()
