"""Foreground-window discovery and activation, gated by the host's PAUSE state.

Does not bypass Windows focus policy, UAC, session isolation or integrity levels.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class WindowManager:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Window management requires Windows")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [ctypes.c_void_p, wintypes.LPWSTR, ctypes.c_int]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.IsWindow.argtypes = [ctypes.c_void_p]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.GetWindowRect.argtypes = [ctypes.c_void_p, ctypes.POINTER(_RECT)]
        self.user32.GetWindowRect.restype = wintypes.BOOL
        self.user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetForegroundWindow.restype = ctypes.c_void_p
        self.user32.IsIconic.argtypes = [ctypes.c_void_p]
        self.user32.IsIconic.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL

    def _entry(self, hwnd):
        u = self.user32
        if not u.IsWindow(hwnd) or not u.IsWindowVisible(hwnd):
            return None
        length = min(u.GetWindowTextLengthW(hwnd), 512)
        if length <= 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        u.GetWindowTextW(hwnd, buf, len(buf))
        title = buf.value.strip()
        if not title:
            return None
        rect = _RECT()
        if not u.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return {"hwnd": int(hwnd.value if isinstance(hwnd, ctypes.c_void_p) else hwnd), "title": title, "pid": pid.value,
                "left": rect.left, "top": rect.top,
                "width": max(0, rect.right-rect.left), "height": max(0, rect.bottom-rect.top)}

    def list_windows(self, limit=80):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be 1..100")
        cbtype = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, wintypes.LPARAM)
        out = []
        def visit(hwnd, _):
            item = self._entry(hwnd)
            if item and item["width"] > 0 and item["height"] > 0:
                out.append(item)
            return len(out) < limit
        cb = cbtype(visit)
        enum = self.user32.EnumWindows
        enum.argtypes = [cbtype, wintypes.LPARAM]
        enum.restype = wintypes.BOOL
        # FALSE is expected when the user-set cap is reached and callback stops enumeration.
        enum(cb, 0)
        return out

    def activate(self, hwnd):
        if type(hwnd) is not int or not 0 < hwnd < 2**64:
            raise ValueError("hwnd must be a positive integer from computer_windows")
        target = ctypes.c_void_p(hwnd)
        item = self._entry(target)
        if item is None:
            raise ValueError("Window is closed, hidden or has no title")
        if self.user32.IsIconic(target):
            self.user32.ShowWindow(target, 9)  # SW_RESTORE
        if not self.user32.SetForegroundWindow(target):
            raise RuntimeError("Windows denied foreground activation; click the window manually")
        if self.user32.GetForegroundWindow() != hwnd:
            raise RuntimeError("Window did not become foreground; Windows focus rules may block it")
        return f"Focused window '{item['title']}' (hwnd={hwnd})"
