---
name: computer-use
description: Safely operate the user's visible Windows desktop through the visual_computer MCP tools with explicit on-screen permission and screenshot verification.
compatibility: OpenCode on Windows with OpenCode Visual Control MCP
---

# Visual desktop workflow

- Only interact with the user's local Windows session when the user explicitly asks for computer actions.
- Begin with `visual_computer_computer_status`. If access is paused, explain that the user must **physically click RESUME** in the persistent on-screen bar. Do not attempt to bypass the permission gate.
- Screenshot with `visual_computer_computer_screenshot` and inspect it before choosing pixel coordinates. On resized screenshots, convert to original screen coordinates using the primary-screen dimensions from status. For precision, use max_width=1920.
- Use `visual_computer_computer_move`, `visual_computer_computer_click`, `visual_computer_computer_drag`, `visual_computer_computer_scroll`, `visual_computer_computer_type`, and `visual_computer_computer_hotkey` for visible action only.
- Verify the result after meaningful actions using a fresh screenshot. Do not assume success from a click alone.
- Pause and ask for the user's decision before sending messages, purchases, deletion, changing settings, or any irreversible action. Never access secrets, credentials, or private content unless necessary and explicitly approved.
- ESC is the user's global **emergency stop**. Automation must not press Esc or try to resume itself. The host starts PAUSED each time; only a user click can authorize access.
- The mouse really moves. Do not move it needlessly; keep actions understandable. Avoid simultaneous user and agent interaction.
- Typing is layout-independent: `computer_type` and `computer_hotkey` go through `SendInput`, so Cyrillic, Latin and other Unicode text work regardless of the active keyboard layout, and the clipboard is not modified.
- The implementation currently uses **primary monitor** coordinates; it does not control elevated windows or the secure desktop.
