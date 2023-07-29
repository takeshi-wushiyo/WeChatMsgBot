import subprocess
import tkinter as tk
from tkinter import filedialog
from tkinter import messagebox

def run_autohotkey_script():
    # Create a root window and hide it
    root = tk.Tk()
    root.withdraw()

    # Open a file dialog and get the path to AutoHotkey.exe
    autohotkey_path = filedialog.askopenfilename(
        title="Select AutoHotkey.exe. The file is usually located in the Program Files folder and is named AutoHotkey.exe"
    )

    # Run the script with the chosen AutoHotkey executable
    subprocess.run([autohotkey_path, r'.\WeChat-Contact-main\wechat-contact.ahk'])

def ask_to_run_script():
    # Ask the user if they want to run the script
    run_script = messagebox.askyesno(
        title="Run AutoHotkey Script?",
        message="Do you want to run the AutoHotkey script?"
    )

    # If the user said yes, run the script
    if run_script:
        run_autohotkey_script()

# Ask the user to run the script
ask_to_run_script()

# Continue with the rest of your code
import sendSMS2wxauto
