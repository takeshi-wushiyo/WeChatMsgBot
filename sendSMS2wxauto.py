import pandas as pd
import pygetwindow as gw
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from wxauto import WeChat
import time

def check_wechat_window():
    try:
        # Try to get the WeChat window
        wechat_window = gw.getWindowsWithTitle('微信')[0]
    except IndexError:
        # If the list is empty, then the WeChat window is not open
        return False

    # Check if the WeChat window is minimized or not visible
    if wechat_window.isMinimized or not wechat_window.visible:
        return False

    # If none of the above conditions are true, then the WeChat window is open and not hidden
    return True

# Create a root window and hide it
root = tk.Tk()
root.withdraw()

# Open a file dialog and get the path to the CSV file
csv_path = filedialog.askopenfilename(
    title="请选择一个CSV文件。文件应包含 'G' 列作为发送标志， 'H' 列作为称呼， 'I' 列作为消息内容。",
    filetypes=[("CSV文件", "*.csv")]
)

# Check the WeChat window
if check_wechat_window():
    # Read the CSV file
    df = pd.read_csv(csv_path)

    # Filter rows where the 7th column (0-indexed) is marked as "发送"
    df_send = df[df.iloc[:, 6] == "发送"]

    # Check if there are any rows marked as "发送"
    if df_send.empty:
        messagebox.showinfo("信息", "没有任何行标记为 '发送'。你是否忘记添加 '发送'？")
    else:
        # Get the contact names from the 2nd column (0-indexed)
        contacts = df_send.iloc[:, 1]

        # Get the contact names from the 8th column (0-indexed)
        appellations = df_send.iloc[:, 7]

        # Get the message contents from the 9th column (0-indexed)
        messages = df_send.iloc[:, 8]

        # Create a WeChat instance
        wx = WeChat()

        # Loop through the contacts and send the corresponding message to each one
        for contact, appellation, msg in zip(contacts, appellations, messages):
            wx.ChatWith(contact)
            wx.SendMsg(appellation + '  ' + msg)  # concatenate the appellation and message
            time.sleep(180)  # wait for 3 minutes
else:
    messagebox.showinfo("信息", "请确保微信窗口已打开并且未被隐藏。同时，请确保微信已切换到第一个好友聊天界面。")
