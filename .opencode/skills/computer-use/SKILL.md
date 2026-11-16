---
name: computer-use
description: Safely operate the user's visible Windows desktop through OpenCode Visual Control MCP tools with explicit on-screen permission and screenshot verification.
compatibility: OpenCode on Windows, OpenCode Visual Control v0.2.0
---

# Visual desktop workflow

- Only act on the user's local desktop after a specific user request. Start with `visual_computer_computer_status` and `visual_computer_computer_displays` to determine permission and monitor positions.
- The host starts **PAUSED**. Ask the human to click RESUME on the always-visible bar. Do not bypass or simulate that local approval. Esc is reserved for the user's emergency stop; never inject Esc or resume automatically.
- `visual_computer_computer_screenshot(max_width=1600, monitor_id="all")` sees all monitors; use a monitor ID from `computer_displays` to capture only that display. Screenshots require RESUME.
- Coordinates are **absolute virtual-desktop physical pixels**, not always primary-screen-local. Monitors left/above the primary can have negative x/y. If the screenshot was resized, map image pixels to the source screen rect: `x = origin.left + image_x * rect.width / image_width`, `y = origin.top + image_y * rect.height / image_height`. Round only after mapping.
- Use `visual_computer_computer_windows` to list visible app windows, and `visual_computer_computer_focus_window(hwnd)` for foreground activation. Window titles may be sensitive; both require RESUME. Windows focus restrictions may deny activation; do not attempt to bypass them.
- Use move/click/drag/scroll/type/hotkey for visible, requested actions; verify important effects with a fresh screenshot. Avoid simultaneous user and agent interaction.
- Pause for human approval before sending messages, purchases, changing settings, deleting data, or irreversible actions. Do not access secrets/credentials or private files unless necessary and explicitly approved.
- `computer_type` uses `SendInput` Unicode; the Windows keyboard layout and clipboard are unaffected. Keep the host local-only; do not expose the TCP port externally.
- The agent cannot operate UAC/secure desktop or elevated apps. Some secondary-monitor and DPI cases remain untested; stop when coordinates appear unreliable.
