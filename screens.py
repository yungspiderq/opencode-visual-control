"""Physical-pixel Windows display topology and virtual-desktop capture.

DPI awareness must be configured BEFORE creating Tk windows or importing PyAutoGUI.
All coordinates in the MCP interface are absolute virtual-desktop physical pixels;
secondary screens to the left or above the primary can have negative coordinates.
"""
from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Monitor:
    id: str
    rect: Rect
    primary: bool

    def as_dict(self) -> dict:
        return {"id": self.id, "primary": self.primary, **self.rect.as_dict()}


class DisplayTopology:
    def __init__(self, monitors):
        self.monitors = tuple(monitors)
        if not self.monitors:
            raise RuntimeError("No Windows displays were found")
        if len({m.id for m in self.monitors}) != len(self.monitors):
            raise RuntimeError("Duplicate display identifiers")
        left = min(m.rect.left for m in self.monitors)
        top = min(m.rect.top for m in self.monitors)
        right = max(m.rect.right for m in self.monitors)
        bottom = max(m.rect.bottom for m in self.monitors)
        self.virtual = Rect(left, top, right-left, bottom-top)

    @property
    def primary(self):
        return next((m for m in self.monitors if m.primary), self.monitors[0])

    def contains(self, x, y):
        return any(m.rect.contains(x, y) for m in self.monitors)

    def monitor(self, monitor_id):
        if monitor_id is None or monitor_id == "all":
            return None
        for monitor in self.monitors:
            if monitor.id == monitor_id:
                return monitor
        return self._unknown(monitor_id)

    @staticmethod
    def _unknown(monitor_id):
        raise ValueError(f"Unknown monitor id: {monitor_id}")

    def as_dict(self):
        return {"virtual": self.virtual.as_dict(), "monitors": [m.as_dict() for m in self.monitors],
                "coordinate_system": "absolute_virtual_desktop_physical_pixels"}


def set_dpi_awareness():
    """Select per-monitor-V2 DPI awareness (fallback to per-monitor or system)."""
    if sys.platform != "win32":
        return "not-windows"
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [ctypes.c_void_p]
        user32.SetProcessDpiAwarenessContext.restype = wintypes.BOOL
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            return "per-monitor-v2"
    except (AttributeError, OSError):
        pass
    try:
        shcore = ctypes.WinDLL("shcore", use_last_error=True)
        shcore.SetProcessDpiAwareness.argtypes = [ctypes.c_int]
        if shcore.SetProcessDpiAwareness(2) == 0:
            return "per-monitor"
    except (AttributeError, OSError):
        pass
    try:
        if user32.SetProcessDPIAware():
            return "system-dpi"
    except (AttributeError, OSError):
        pass
    # Another dependency or app manifest may already have configured awareness.
    return "preconfigured-or-unavailable"


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFOEX(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", wintypes.DWORD), ("szDevice", wintypes.WCHAR*32)]


class Win32Displays:
    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("Display enumeration requires Windows")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)

    def topology(self) -> DisplayTopology:
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, ctypes.c_void_p, ctypes.c_void_p,
                                            ctypes.POINTER(_RECT), wintypes.LPARAM)
        monitors = []
        getinfo = self.user32.GetMonitorInfoW
        getinfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(_MONITORINFOEX)]
        getinfo.restype = wintypes.BOOL

        def visit(handle, _hdc, _rect, _data):
            info = _MONITORINFOEX()
            info.cbSize = ctypes.sizeof(info)
            if not getinfo(handle, ctypes.byref(info)):
                return False
            r = info.rcMonitor
            monitors.append(Monitor(info.szDevice, Rect(r.left, r.top, r.right-r.left, r.bottom-r.top),
                                    bool(info.dwFlags & 1)))
            return True

        enum = self.user32.EnumDisplayMonitors
        enum.argtypes = [ctypes.c_void_p, ctypes.c_void_p, callback_type, wintypes.LPARAM]
        enum.restype = wintypes.BOOL
        cb = callback_type(visit)
        if not enum(None, None, cb, 0):
            raise OSError(ctypes.get_last_error(), "Could not enumerate connected monitors")
        return DisplayTopology(sorted(monitors, key=lambda m: (not m.primary, m.rect.left, m.rect.top)))


class VirtualDesktopCapture:
    def __init__(self, topology_provider):
        self.topology_provider = topology_provider

    def capture(self, monitor_id="all"):
        from PIL import ImageGrab
        topology = self.topology_provider()
        selected = topology.monitor(monitor_id)
        image = ImageGrab.grab(all_screens=True)
        if image.size != (topology.virtual.width, topology.virtual.height):
            raise RuntimeError("Display topology changed during capture; retry after refreshing display list")
        if selected:
            box = (selected.rect.left - topology.virtual.left,
                   selected.rect.top - topology.virtual.top,
                   selected.rect.right - topology.virtual.left,
                   selected.rect.bottom - topology.virtual.top)
            image = image.crop(box)
        return image
