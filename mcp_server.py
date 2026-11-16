"""OpenCode MCP tools. Run as a local stdio subprocess."""
from __future__ import annotations

import base64
import json
from mcp.server.fastmcp import FastMCP, Image
from bridge import request

mcp = FastMCP("OpenCode Visual Control")


@mcp.tool()
def computer_status() -> str:
    """Check whether the visible local Windows desktop host is connected and enabled."""
    info = request("status")
    return (f"Host online; control {'ENABLED' if info['enabled'] else 'PAUSED'}; "
            f"{info['monitor_count']} monitors; primary {info['width']}x{info['height']}; "
            f"virtual desktop {info['virtual']}.")


@mcp.tool()
def computer_displays() -> str:
    """List monitors with absolute physical-pixel coordinates (can be negative), plus virtual desktop bounds."""
    return json.dumps(request("displays"), ensure_ascii=False)


@mcp.tool()
def computer_screenshot(max_width: int = 1600, monitor_id: str = "all") -> Image:
    """Screenshot all monitors or a monitor id from computer_displays. Requires RESUME. If resized, scale image x/y back to physical pixels and add monitor/virtual origin before clicking."""
    payload = request("screenshot", max_width=max_width, monitor_id=monitor_id)
    return Image(data=base64.b64decode(payload["image"]), format="png")


@mcp.tool()
def computer_move(x: int, y: int, duration: float = 0.35) -> str:
    """Move real cursor using absolute virtual desktop physical x,y; negatives are valid on left/top monitors. Requires RESUME."""
    return request("move", x=x, y=y, duration=duration)["message"]


@mcp.tool()
def computer_click(x: int, y: int, button: str = "left", count: int = 1) -> str:
    """Move and click the real cursor; highlights the click on the user's screen."""
    return request("click", x=x, y=y, button=button, count=count)["message"]


@mcp.tool()
def computer_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.65) -> str:
    """Drag real cursor even across monitors; ESC/pause interrupts automation."""
    return request("drag", x1=x1, y1=y1, x2=x2, y2=y2, duration=duration)["message"]


@mcp.tool()
def computer_scroll(clicks: int, x: int | None = None, y: int | None = None) -> str:
    """Scroll in the current window, -15..15 steps. Optionally move to x,y first."""
    return request("scroll", clicks=clicks, x=x, y=y)["message"]


@mcp.tool()
def computer_type(text: str) -> str:
    """Type up to 2000 characters into the focused app. Works with any keyboard layout and Unicode text, without changing the clipboard."""
    return request("type", text=text)["message"]


@mcp.tool()
def computer_hotkey(keys: list[str]) -> str:
    """Press 1-4 keys such as ['ctrl','s']; ESC is reserved as emergency stop."""
    return request("hotkey", keys=keys)["message"]


@mcp.tool()
def computer_windows(limit: int = 80) -> str:
    """List visible titled Windows desktop windows with hwnd, title and bounds. Requires RESUME."""
    return json.dumps(request("windows", limit=limit)["windows"], ensure_ascii=False)


@mcp.tool()
def computer_focus_window(hwnd: int) -> str:
    """Restore and focus a previously listed visible Windows window by hwnd. Requires RESUME; Windows may deny focus."""
    return request("focus_window", hwnd=hwnd)["message"]


if __name__ == "__main__":
    mcp.run(transport="stdio")
