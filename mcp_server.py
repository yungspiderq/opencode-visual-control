"""OpenCode MCP tools. Run as a local stdio subprocess."""
from __future__ import annotations

import base64
from mcp.server.fastmcp import FastMCP, Image
from bridge import request

mcp = FastMCP("OpenCode Visual Control")


@mcp.tool()
def computer_status() -> str:
    """Check whether the visible local Windows desktop host is connected and enabled."""
    info = request("status")
    return f"Host online; control {'ENABLED' if info['enabled'] else 'PAUSED'}; primary screen {info['width']}x{info['height']}."


@mcp.tool()
def computer_screenshot(max_width: int = 1600) -> Image:
    """View the CURRENT primary Windows desktop. Requires the user's visible RESUME approval. Image coordinates may be scaled; request full width for exact pixel positions."""
    payload = request("screenshot", max_width=max_width)
    return Image(data=base64.b64decode(payload["image"]), format="png")


@mcp.tool()
def computer_move(x: int, y: int, duration: float = 0.35) -> str:
    """Smoothly move the REAL Windows mouse cursor to primary-screen x,y. Only when authorized."""
    return request("move", x=x, y=y, duration=duration)["message"]


@mcp.tool()
def computer_click(x: int, y: int, button: str = "left", count: int = 1) -> str:
    """Move and click the real cursor; highlights the click on the user's screen."""
    return request("click", x=x, y=y, button=button, count=count)["message"]


@mcp.tool()
def computer_drag(x1: int, y1: int, x2: int, y2: int, duration: float = 0.65) -> str:
    """Drag with the real cursor on the primary monitor; ESC/pause interrupts automation."""
    return request("drag", x1=x1, y1=y1, x2=x2, y2=y2, duration=duration)["message"]


@mcp.tool()
def computer_scroll(clicks: int, x: int | None = None, y: int | None = None) -> str:
    """Scroll in the current window, -15..15 steps. Optionally move to x,y first."""
    return request("scroll", clicks=clicks, x=x, y=y)["message"]


@mcp.tool()
def computer_type(text: str) -> str:
    """Type up to 2000 characters into the focused app. Unicode text uses clipboard paste and replaces clipboard content; do not use for secrets."""
    return request("type", text=text)["message"]


@mcp.tool()
def computer_hotkey(keys: list[str]) -> str:
    """Press 1-4 keys such as ['ctrl','s']; ESC is reserved as emergency stop."""
    return request("hotkey", keys=keys)["message"]


if __name__ == "__main__":
    mcp.run(transport="stdio")
