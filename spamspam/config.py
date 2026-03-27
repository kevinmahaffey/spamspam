"""State management for SpamSpam. Persists to ~/.config/spamspam/state.json."""

import fcntl
import json
import os
import shutil
from pathlib import Path

STATE_DIR = Path.home() / ".config" / "spamspam"
STATE_FILE = STATE_DIR / "state.json"

DEFAULT_STATE = {
    "self_handle": None,
    "last_command_rowid": 0,
    "flagged": {},
}


def _ensure_dir():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


def load_state() -> dict:
    _ensure_dir()
    if not STATE_FILE.exists():
        return dict(DEFAULT_STATE)
    try:
        with open(STATE_FILE, "r") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                state = json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        # Merge with defaults for any missing keys
        for key, val in DEFAULT_STATE.items():
            if key not in state:
                state[key] = val if not isinstance(val, dict) else dict(val)
        return state
    except (json.JSONDecodeError, ValueError):
        # Corrupt file - back it up and start fresh
        backup = STATE_FILE.with_suffix(".json.bak")
        shutil.copy2(STATE_FILE, backup)
        print(f"[WARN] Corrupt state file, backed up to {backup}")
        return dict(DEFAULT_STATE)


def save_state(state: dict):
    _ensure_dir()
    tmp = STATE_FILE.with_suffix(".json.tmp")
    with open(tmp, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            json.dump(state, f, indent=2)
            f.write("\n")
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
    os.replace(tmp, STATE_FILE)


def flag_number(number: str, persona: str, service: str = "SMS",
                last_message_id: int = 0):
    state = load_state()
    state["flagged"][number] = {
        "persona": persona,
        "service": service,
        "last_reply_message_id": last_message_id,
        "conversation_history": [],
        "active": True,
    }
    save_state(state)


def unflag_number(number: str):
    state = load_state()
    if number in state["flagged"]:
        del state["flagged"][number]
        save_state(state)
        return True
    return False


def get_flagged() -> dict:
    return load_state().get("flagged", {})


def set_self_handle(handle: str):
    state = load_state()
    state["self_handle"] = handle
    save_state(state)


def get_self_handle() -> str | None:
    return load_state().get("self_handle")
