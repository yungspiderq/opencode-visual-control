"""Validated, cancellable Windows GUI automation primitives.

No network, shell, arbitrary code execution or hidden remote operation.
"""
from __future__ import annotations

import ctypes
import math
import threading
import time
from ctypes import wintypes


class ControlStopped(RuntimeError):
    pass


# --- Layout-independent keyboard input -------------------------------------
# PyAutoGUI builds its key table with VkKeyScan against the keyboard layout that
# is active when it is imported.  On a non-US layout (for example Russian) every
# Latin letter maps to -1 and PyAutoGUI silently drops it, so "write" types only
# digits and punctuation and hotkey("ctrl", "v") presses nothing at all.
# SendInput with KEYEVENTF_UNICODE has no layout dependency.

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD), ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


VK_NAMES = {
    "ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B,
    "enter": 0x0D, "tab": 0x09, "space": 0x20, "backspace": 0x08,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "up": 0x26, "down": 0x28,
    "left": 0x25, "right": 0x27, "esc": 0x1B,
}
VK_NAMES.update({f"f{i}": 0x6F + i for i in range(1, 13)})


def virtual_key(name: str) -> int:
    """Virtual-key code for an allowed key name, independent of keyboard layout."""
    if name in VK_NAMES:
        return VK_NAMES[name]
    if len(name) == 1 and name.isascii() and name.isalnum():
        return ord(name.upper())  # VK_A..VK_Z, VK_0..VK_9
    raise ValueError("Unsupported key name")


class KeySender:
    """Send keystrokes with SendInput so any layout can type any character."""

    def __init__(self):
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

    @staticmethod
    def _key(vk=0, scan=0, flags=0):
        return _INPUT(type=_INPUT_KEYBOARD,
                      union=_INPUTUNION(ki=_KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=None)))

    def _send(self, events):
        if not events:
            return
        array = (_INPUT * len(events))(*events)
        sent = self.user32.SendInput(len(events), array, ctypes.sizeof(_INPUT))
        if sent != len(events):
            raise OSError(ctypes.get_last_error(), "SendInput was blocked by the system")

    def press(self, vk: int) -> None:
        self._send([self._key(vk=vk), self._key(vk=vk, flags=_KEYEVENTF_KEYUP)])

    def combo(self, keys) -> None:
        codes = [virtual_key(k) for k in keys]
        events = [self._key(vk=c) for c in codes]
        events += [self._key(vk=c, flags=_KEYEVENTF_KEYUP) for c in reversed(codes)]
        self._send(events)

    def type_char(self, char: str, gate) -> None:
        # Windows text input is UTF-16: split astral characters into surrogate units.
        raw = char.encode("utf-16-le")
        for i in range(0, len(raw), 2):
            unit = int.from_bytes(raw[i:i + 2], "little")
            gate.check()
            self._send([self._key(scan=unit, flags=_KEYEVENTF_UNICODE),
                        self._key(scan=unit, flags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP)])


class SafetyGate:
    """Automation starts paused and is only resumed by a human UI action."""

    def __init__(self):
        self._enabled = threading.Event()
        self._stop = threading.Event()

    @property
    def enabled(self) -> bool:
        return self._enabled.is_set()

    def resume(self) -> None:
        self._stop.clear()
        self._enabled.set()

    def pause(self) -> None:
        self._enabled.clear()
        self._stop.set()

    def check(self) -> None:
        if not self._enabled.is_set() or self._stop.is_set():
            raise ControlStopped("Control paused. Press RESUME on the local indicator to authorize access.")


class DesktopActions:
    MAX_TEXT = 2000
    MAX_DURATION = 3.0
    MAX_STEPS = 240
    ALLOWED_BUTTONS = {"left", "right", "middle"}
    ALLOWED_KEYS = {
        "ctrl", "alt", "shift", "win", "enter", "tab", "space", "backspace",
        "delete", "up", "down", "left", "right", "home", "end", "pageup",
        "pagedown", "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8",
        "f9", "f10", "f11", "f12", "insert", "esc",
    } | set("abcdefghijklmnopqrstuvwxyz0123456789")

    def __init__(self, gui, gate: SafetyGate, click_effect=None, keys=None):
        self.gui = gui
        self.gate = gate
        self.click_effect = click_effect or (lambda x, y: None)
        self.keys = keys or KeySender()
        self.gui.FAILSAFE = True  # upper-left corner triggers PyAutoGUI fail-safe
        self.gui.PAUSE = 0.0

    @staticmethod
    def _finite_number(v, field, lo, hi) -> float:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not lo <= v <= hi:
            raise ValueError(f"{field} must be a number between {lo} and {hi}")
        return float(v)

    def _point(self, x, y) -> tuple[int, int]:
        width, height = self.gui.size()
        xf = self._finite_number(x, "x", 0, width - 1)
        yf = self._finite_number(y, "y", 0, height - 1)
        return round(xf), round(yf)

    def move(self, x, y, duration=0.35) -> str:
        self.gate.check()
        x, y = self._point(x, y)
        duration = self._finite_number(duration, "duration", 0, self.MAX_DURATION)
        old = self.gui.position()
        ox, oy = old[0], old[1]
        if duration == 0:
            self.gui.moveTo(x, y)
        else:
            steps = min(self.MAX_STEPS, max(2, round(duration * 60)))
            for i in range(1, steps + 1):
                self.gate.check()
                t = i / steps
                t = t * t * (3 - 2 * t)  # smoothstep easing
                self.gui.moveTo(round(ox + (x - ox) * t), round(oy + (y - oy) * t))
                time.sleep(duration / steps)
        self.gate.check()
        return f"Moved native mouse pointer to ({x}, {y})"

    def click(self, x, y, button="left", count=1) -> str:
        if button not in self.ALLOWED_BUTTONS:
            raise ValueError("Unsupported mouse button")
        if count not in (1, 2):
            raise ValueError("count must be 1 or 2")
        x, y = self._point(x, y)
        self.move(x, y)
        self.gate.check()
        self.gui.click(x=x, y=y, button=button, clicks=count, interval=0.12)
        self.click_effect(x, y)
        return f"Clicked {button} x{count} at ({x}, {y})"

    def drag(self, x1, y1, x2, y2, duration=0.65) -> str:
        x1, y1 = self._point(x1, y1)
        x2, y2 = self._point(x2, y2)
        duration = self._finite_number(duration, "duration", 0, self.MAX_DURATION)
        self.move(x1, y1, 0.3)
        self.gate.check()
        self.gui.mouseDown(button="left")
        try:
            self.move(x2, y2, duration)
        finally:
            self.gui.mouseUp(button="left")
        return f"Dragged ({x1},{y1}) -> ({x2},{y2})"

    def scroll(self, clicks, x=None, y=None) -> str:
        self.gate.check()
        if isinstance(clicks, bool) or not isinstance(clicks, int) or not -15 <= clicks <= 15:
            raise ValueError("clicks must be an integer from -15 to 15")
        if (x is None) != (y is None):
            raise ValueError("x and y must both be specified or both omitted")
        if x is not None:
            self.move(x, y, 0.2)
        self.gate.check()
        self.gui.scroll(clicks)
        return f"Scrolled {clicks} steps"

    def type_text(self, text, interval=0.012) -> str:
        self.gate.check()
        if not isinstance(text, str) or len(text) > self.MAX_TEXT:
            raise ValueError("text must contain at most 2000 characters")
        interval = self._finite_number(interval, "interval", 0, 0.05)
        for char in text:
            if char in "\r\n":
                self.gate.check()
                self.keys.press(VK_NAMES["enter"])
            elif char == "\t":
                self.gate.check()
                self.keys.press(VK_NAMES["tab"])
            else:
                self.keys.type_char(char, self.gate)
            if interval:
                time.sleep(interval)
        return f"Typed {len(text)} characters"

    def hotkey(self, keys) -> str:
        self.gate.check()
        if not isinstance(keys, list) or not 1 <= len(keys) <= 4:
            raise ValueError("keys must be a list of 1-4 allowed names")
        lower = [k.lower() if isinstance(k, str) else "" for k in keys]
        if any(k not in self.ALLOWED_KEYS for k in lower):
            raise ValueError("Unsupported key name")
        if "esc" in lower:
            raise ValueError("Esc is reserved for the user's emergency stop")
        self.gate.check()
        self.keys.combo(lower)
        return "Pressed " + "+".join(lower)

    def screenshot_png(self, max_width=1600) -> bytes:
        self.gate.check()
        max_width = int(self._finite_number(max_width, "max_width", 320, 1920))
        import io
        from PIL import Image
        picture = self.gui.screenshot()
        if picture.width > max_width:
            ratio = max_width / picture.width
            picture = picture.resize((max_width, max(1, round(picture.height * ratio))), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        picture.save(buf, format="PNG", optimize=False)
        return buf.getvalue()
