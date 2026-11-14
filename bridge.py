"""Local-only authenticated requests from the MCP subprocess to the UI host."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PORT = 48721
HOST = "127.0.0.1"
STATE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local")) / "OpenCodeVisualControl"
TOKEN_FILE = STATE_DIR / "host.token"


class BridgeError(RuntimeError):
    pass


def request(action: str, **payload):
    try:
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError as e:
        raise BridgeError("Desktop host is not running. Start 'start-host.ps1' first.") from e
    body = json.dumps({"action": action, "payload": payload}, ensure_ascii=False).encode("utf-8")
    req = Request(
        f"http://{HOST}:{PORT}/action",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-Visual-Control-Token": token},
    )
    try:
        with urlopen(req, timeout=20) as resp:
            result = json.load(resp)
    except HTTPError as e:
        try:
            details = json.load(e).get("error", str(e))
        except Exception:
            details = str(e)
        raise BridgeError(details) from e
    except (URLError, TimeoutError) as e:
        raise BridgeError("Desktop host is unavailable. Open start-host.ps1 and press RESUME.") from e
    if not result.get("ok"):
        raise BridgeError(result.get("error", "Unknown host error"))
    return result
