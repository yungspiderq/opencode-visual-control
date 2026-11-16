"""Windows-only local desktop controller with a persistent visible safety bar.

The host has no external network listener and no shell-execution capability.
The user starts it directly and must click RESUME before any screen access.
"""
from __future__ import annotations

import base64
import ctypes
import hmac
import json
import os
import queue
import secrets
import sys
import threading
import tkinter as tk
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from actions import DesktopActions, SafetyGate
from bridge import HOST, PORT, STATE_DIR, TOKEN_FILE
from screens import Win32Displays, VirtualDesktopCapture, set_dpi_awareness
from windows import WindowManager


def _place_physical(widget, x, y, width, height):
    """Position a Tk toplevel by Win32 physical coordinates, including negative ones.

    Tk geometry strings use negative offsets as distances from the screen edge;
    SetWindowPos avoids that ambiguity for screens left/above the primary.
    """
    widget.update_idletasks()
    if sys.platform != "win32":
        widget.geometry(f"{width}x{height}{x:+d}{y:+d}")
        return
    hwnd_text = widget.wm_frame()
    hwnd = int(hwnd_text, 0) if isinstance(hwnd_text, str) else int(hwnd_text)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
    user32.SetWindowPos.restype = ctypes.c_int
    if not user32.SetWindowPos(ctypes.c_void_p(hwnd), None, int(x), int(y),
                               int(width), int(height), 0x0004 | 0x0010 | 0x0040):
        raise OSError(ctypes.get_last_error(), "Unable to position overlay")


class VisualHost:
    def __init__(self, gui, keyboard_module):
        self.gui = gui
        self.keyboard_module = keyboard_module
        self.gate = SafetyGate()  # intentionally PAUSED on startup
        self.busy = threading.Lock()
        self.events = queue.SimpleQueue()
        self.token = secrets.token_urlsafe(40)
        self.displays = Win32Displays()
        self.capture = VirtualDesktopCapture(self.displays.topology)
        self.windows = WindowManager()
        self.desktop = DesktopActions(gui, self.gate, self.flash_click,
                                      topology_provider=self.displays.topology,
                                      capture=self.capture.capture)
        self.server = None
        self._active = False
        self._idle_generation = 0

        self.root = tk.Tk()
        self.root.title("OpenCode Visual Control")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#0d111b")
        self.root.geometry(self._bar_geometry())

        bar = tk.Frame(self.root, bg="#0d111b", highlightthickness=1, highlightbackground="#30384a")
        bar.pack(fill="both", expand=True)
        self.dot = tk.Label(bar, text="●", fg="#f9b454", bg="#0d111b", font=("Segoe UI", 17))
        self.dot.pack(side="left", padx=(12, 8))
        mid = tk.Frame(bar, bg="#0d111b")
        mid.pack(side="left", fill="both", expand=True)
        self.title_label = tk.Label(mid, text="OpenCode: управление приостановлено", fg="#f1f5fd", bg="#0d111b", font=("Segoe UI Semibold", 10), anchor="w")
        self.title_label.pack(fill="x", pady=(10, 0))
        self.sub = tk.Label(mid, text="Esc — стоп · Только локальный доступ", fg="#9ba6bb", bg="#0d111b", font=("Segoe UI", 8), anchor="w")
        self.sub.pack(fill="x", pady=(0, 8))
        self.toggle = tk.Button(bar, text="RESUME", command=self._toggle, bg="#2463eb", fg="white", activebackground="#3776ff", activeforeground="white", relief="flat", font=("Segoe UI Semibold", 9), padx=10, pady=8, cursor="hand2")
        self.toggle.pack(side="left", padx=(3, 5))
        self.close_button = tk.Button(bar, text="✕", command=self._shutdown, bg="#2c3444", fg="white", activebackground="#e14952", activeforeground="white", relief="flat", font=("Segoe UI", 10), padx=9, pady=7, cursor="hand2")
        self.close_button.pack(side="left", padx=(0, 9))
        for widget in (self.root, bar, mid, self.dot, self.title_label, self.sub):
            widget.bind("<Button-1>", self._drag_start)
            widget.bind("<B1-Motion>", self._drag_motion)
        self._click_circle = None
        p = self.displays.topology().primary.rect
        _place_physical(self.root, p.left+(p.width-470)//2, p.top+18, 470, 64)
        self.root.after(35, self._pump)

        self.keyboard_listener = self.keyboard_module.Listener(on_press=self._on_key)
        self.keyboard_listener.daemon = True

    def _bar_geometry(self):
        w = 470
        primary = self.displays.topology().primary.rect
        x = primary.left + (primary.width - w) // 2
        y = primary.top + 18
        return f"{w}x64{x:+d}{y:+d}"

    def _drag_start(self, e):
        self._drag_x, self._drag_y = e.x_root, e.y_root

    def _drag_motion(self, e):
        if not hasattr(self, "_drag_x"):
            return
        dx, dy = e.x_root - self._drag_x, e.y_root - self._drag_y
        if abs(dx) < 3 and abs(dy) < 3:
            return
        _place_physical(self.root, self.root.winfo_x()+dx, self.root.winfo_y()+dy,
                        self.root.winfo_width(), self.root.winfo_height())
        self._drag_x, self._drag_y = e.x_root, e.y_root

    def _on_key(self, key):
        if key == self.keyboard_module.Key.esc:
            self.gate.pause()
            self.events.put(("paused", None))

    def _toggle(self):
        if self.gate.enabled:
            self.gate.pause()
        else:
            self.gate.resume()  # only a physical click on RESUME enables automation
        self._paint()

    def _paint(self):
        enabled = self.gate.enabled
        self.dot.configure(fg="#36d899" if enabled else "#f9b454")
        self.title_label.configure(text=("OpenCode управляет вашим компьютером" if self._active and enabled else "OpenCode: доступ разрешён" if enabled else "OpenCode: управление приостановлено"))
        self.toggle.configure(text="PAUSE" if enabled else "RESUME", bg="#343e54" if enabled else "#2463eb")

    def _pump(self):
        while True:
            try:
                event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "active":
                self._active = True
                self._idle_generation += 1
            elif event == "idle":
                self._idle_generation += 1
                current = self._idle_generation
                self.root.after(1200, lambda gen=current: self._mark_idle(gen))
            elif event == "paused":
                self._active = False
            elif event == "click":
                self._show_click(*payload)
            self._paint()
        self.root.after(35, self._pump)

    def _mark_idle(self, generation):
        if self._idle_generation == generation:
            self._active = False
            self._paint()

    def flash_click(self, x, y):
        self.events.put(("click", (x, y)))

    def _show_click(self, x, y):
        # A separate click-through window lets the actual Windows cursor remain usable.
        if self._click_circle:
            try:
                self._click_circle.destroy()
            except tk.TclError:
                pass
        popup = tk.Toplevel(self.root)
        self._click_circle = popup
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        chroma = "#010203"
        popup.configure(bg=chroma)
        popup.geometry("68x68+0+0")
        try:
            popup.wm_attributes("-transparentcolor", chroma)
        except tk.TclError:
            popup.attributes("-alpha", 0.5)
        canvas = tk.Canvas(popup, width=68, height=68, bg=chroma, highlightthickness=0)
        canvas.pack()
        canvas.create_oval(7, 7, 61, 61, outline="#22dbff", width=3)
        canvas.create_oval(22, 22, 46, 46, outline="#91f0ff", width=2)
        try:
            hwnd = popup.winfo_id()
            GWL_EXSTYLE, WS_EX_TRANSPARENT, WS_EX_LAYERED = -20, 0x20, 0x80000
            getlong = ctypes.windll.user32.GetWindowLongW
            setlong = ctypes.windll.user32.SetWindowLongW
            setlong(hwnd, GWL_EXSTYLE, getlong(hwnd, GWL_EXSTYLE) | WS_EX_TRANSPARENT | WS_EX_LAYERED)
            ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0x00030201, 0, 0x1)
        except Exception:
            pass
        _place_physical(popup, x-34, y-34, 68, 68)
        popup.after(440, lambda: popup.destroy() if popup.winfo_exists() else None)

    def _shutdown(self):
        self.gate.pause()
        self.keyboard_listener.stop()
        if self.server:
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        try:
            TOKEN_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        self.root.destroy()

    def perform(self, action, payload):
        if action == "status":
            topo = self.displays.topology()
            return {"enabled": self.gate.enabled, "width": topo.primary.rect.width,
                    "height": topo.primary.rect.height, "virtual": topo.virtual.as_dict(),
                    "monitor_count": len(topo.monitors)}
        if action == "displays":
            return self.displays.topology().as_dict()
        self.gate.check()
        with self.busy:
            self.gate.check()
            self.events.put(("active", None))
            try:
                if action == "screenshot":
                    raw = self.desktop.screenshot_png(payload.get("max_width", 1600), payload.get("monitor_id", "all"))
                    return {"image": base64.b64encode(raw).decode("ascii")}
                if action == "windows":
                    return {"windows": self.windows.list_windows(payload.get("limit", 80))}
                if action == "focus_window":
                    output = self.windows.activate(payload.get("hwnd"))
                elif action == "move":
                    output = self.desktop.move(payload.get("x"), payload.get("y"), payload.get("duration", 0.35))
                elif action == "click":
                    output = self.desktop.click(payload.get("x"), payload.get("y"), payload.get("button", "left"), payload.get("count", 1))
                elif action == "drag":
                    output = self.desktop.drag(payload.get("x1"), payload.get("y1"), payload.get("x2"), payload.get("y2"), payload.get("duration", 0.65))
                elif action == "scroll":
                    output = self.desktop.scroll(payload.get("clicks"), payload.get("x"), payload.get("y"))
                elif action == "type":
                    output = self.desktop.type_text(payload.get("text"))
                elif action == "hotkey":
                    output = self.desktop.hotkey(payload.get("keys"))
                else:
                    raise ValueError("Unsupported action")
                return {"message": output}
            finally:
                self.events.put(("idle", None))

    def run(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        host = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return  # no screen/input payloads logged

            def do_POST(self):
                if self.path != "/action":
                    self._send(404, {"ok": False, "error": "Not found"})
                    return
                if not hmac.compare_digest(self.headers.get("X-Visual-Control-Token", ""), host.token):
                    self._send(403, {"ok": False, "error": "Forbidden"})
                    return
                try:
                    size = int(self.headers.get("Content-Length", "0"))
                    if size < 0 or size > 16384:
                        raise ValueError("Request too large")
                    body = json.loads(self.rfile.read(size))
                    if not isinstance(body, dict) or not isinstance(body.get("action"), str) or not isinstance(body.get("payload"), dict):
                        raise ValueError("Invalid request")
                    result = host.perform(body["action"], body["payload"])
                    self._send(200, {"ok": True, **result})
                except Exception as e:
                    self._send(400, {"ok": False, "error": str(e)})

            def _send(self, code, body):
                out = json.dumps(body, ensure_ascii=False).encode("utf-8")
                self.send_response(code)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(out)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                try:
                    self.wfile.write(out)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        try:
            self.server = ThreadingHTTPServer((HOST, PORT), Handler)
        except OSError as e:
            raise RuntimeError(f"Host port {PORT} already in use. Close the previous instance.") from e
        # Only write the token AFTER the bind succeeds; a second instance must
        # never invalidate the already-running host's authorization file.
        TOKEN_FILE.write_text(self.token, encoding="utf-8")
        self.keyboard_listener.start()
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print("OpenCode Visual Control running: local-only host, paused until RESUME")
        try:
            self.root.mainloop()
        finally:
            self.gate.pause()
            self.server.server_close()
            TOKEN_FILE.unlink(missing_ok=True)


def main():
    if sys.platform != "win32":
        raise SystemExit("This host requires Windows 10/11 and an interactive desktop.")
    awareness = set_dpi_awareness()  # BEFORE PyAutoGUI import and Tk root creation
    print(f"DPI awareness: {awareness}")
    import pyautogui
    from pynput import keyboard
    app = VisualHost(pyautogui, keyboard)
    app.run()


if __name__ == "__main__":
    main()
