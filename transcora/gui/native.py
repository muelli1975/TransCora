"""Keep the native Windows caption consistent with the dark application."""
import ctypes
from ctypes import wintypes
import sys
import tkinter as tk


def dark_titlebar(window):
    if sys.platform != "win32":
        return
    try:
        user32 = ctypes.WinDLL("user32")
        dwm = ctypes.WinDLL("dwmapi")
        user32.GetAncestor.argtypes = (wintypes.HWND, wintypes.UINT)
        user32.GetAncestor.restype = wintypes.HWND
        dwm.DwmSetWindowAttribute.argtypes = (
            wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        dwm.DwmSetWindowAttribute.restype = ctypes.c_long
        # Tk's widget HWND is inside the native window that owns the caption.
        hwnd = user32.GetAncestor(window.winfo_id(), 2)  # GA_ROOT
        if not hwnd:
            return
        enabled = wintypes.BOOL(1)
        result = dwm.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enabled), ctypes.sizeof(enabled))
        if result != 0:
            # Earlier Windows 10 builds used attribute 19 for dark captions.
            dwm.DwmSetWindowAttribute(hwnd, 19, ctypes.byref(enabled), ctypes.sizeof(enabled))
        # Match the other Stereo tools (CustomTkinter dark appearance): request
        # Windows' dark frame, leaving caption and text colors to the system.
        user32.SetWindowPos.argtypes = (
            wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, wintypes.UINT)
        user32.SetWindowPos.restype = wintypes.BOOL
        # Repaint the frame without moving, resizing or activating the window.
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0, 0x0037)
    except (OSError, AttributeError, tk.TclError):
        # Caption customization is optional on older Windows versions.
        pass
