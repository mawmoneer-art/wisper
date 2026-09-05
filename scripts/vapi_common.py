"""Shared helpers for the Vapi scripts. Python 3.9+, standard library only."""
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / ".vapi" / "state.json"
API = "https://api.vapi.ai"


def load_env():
    """Read KEY=VALUE lines from .env at the repo root into os.environ (no override)."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require(name, hint=""):
    value = os.environ.get(name)
    if not value:
        print(f"Missing {name}. {hint}".strip(), file=sys.stderr)
        sys.exit(1)
    return value


def api(method, path, body=None):
    token = require("VAPI_API_KEY", "Put it in .env as VAPI_API_KEY=... (Dashboard > Org settings > API keys).")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        print(f"Vapi API error {e.code} on {method} {path}:\n{detail}", file=sys.stderr)
        sys.exit(1)


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2) + "\n")
