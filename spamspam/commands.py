"""Parse self-text commands from the user's own iMessage conversation."""

import re

from . import config, db, personas, sender


def parse_command(text: str) -> dict | None:
    """Parse a self-text message into a command.

    Supported commands:
        spam +15551234567              -> flag with random persona
        spam +15551234567 alien        -> flag with specific persona
        stop +15551234567              -> unflag
        list                           -> list flagged numbers
        personas                       -> list available personas
        status                         -> show bot status

    Returns dict with 'action' and relevant params, or None if not a command.
    """
    text = text.strip().lower()

    if not text:
        return None

    # "spam <number> [persona]"
    match = re.match(
        r"^spam\s+([\+]?[\d\-\(\)\s]{7,20})\s*(\w+)?$", text
    )
    if match:
        number = _normalize_number(match.group(1))
        persona_key = match.group(2)
        return {"action": "flag", "number": number, "persona": persona_key}

    # "stop <number>"
    match = re.match(r"^stop\s+([\+]?[\d\-\(\)\s]{7,20})$", text)
    if match:
        number = _normalize_number(match.group(1))
        return {"action": "unflag", "number": number}

    # "list"
    if text == "list":
        return {"action": "list"}

    # "personas"
    if text in ("personas", "persona"):
        return {"action": "personas"}

    # "status"
    if text == "status":
        return {"action": "status"}

    return None


def _normalize_number(raw: str) -> str:
    """Normalize a phone number to a clean format."""
    digits = re.sub(r"[^\d+]", "", raw)
    # If it's 10 digits without +, assume US and add +1
    if len(digits) == 10 and not digits.startswith("+"):
        digits = "+1" + digits
    elif not digits.startswith("+"):
        digits = "+" + digits
    return digits


def execute_command(cmd: dict, self_handle: str, dry_run: bool = False) -> str:
    """Execute a parsed command and return a status message."""
    action = cmd["action"]

    if action == "flag":
        number = cmd["number"]
        persona_key = cmd.get("persona")

        # Validate persona if specified
        if persona_key and persona_key not in personas.PERSONAS:
            available = ", ".join(personas.PERSONAS.keys())
            msg = f"Unknown persona '{persona_key}'. Available: {available}"
            _reply_to_self(self_handle, msg, dry_run)
            return msg

        # Pick persona
        if persona_key:
            persona = personas.PERSONAS[persona_key]
        else:
            persona_key, persona = personas.pick_persona()

        # Get latest message ID and service type
        try:
            latest_rowid = db.get_latest_rowid_for_handle(number)
            service = db.detect_service_for_handle(number)
        except Exception:
            latest_rowid = 0
            service = "SMS"

        config.flag_number(number, persona_key, service, latest_rowid)

        msg = (
            f"Flagged {number} as {persona['name']} ({persona_key}). "
            f"Bot will engage via {service}. "
            f"Remember to mute that conversation!"
        )
        _reply_to_self(self_handle, msg, dry_run)
        return msg

    elif action == "unflag":
        number = cmd["number"]
        if config.unflag_number(number):
            msg = f"Stopped engaging with {number}."
        else:
            msg = f"{number} was not flagged."
        _reply_to_self(self_handle, msg, dry_run)
        return msg

    elif action == "list":
        flagged = config.get_flagged()
        if not flagged:
            msg = "No numbers currently flagged."
        else:
            lines = []
            for num, entry in flagged.items():
                status = "active" if entry.get("active", True) else "paused"
                persona_key = entry.get("persona", "unknown")
                name = personas.PERSONAS.get(persona_key, {}).get("name", "?")
                exchanges = len(entry.get("conversation_history", [])) // 2
                lines.append(f"{num}: {name} ({persona_key}) - {exchanges} exchanges - {status}")
            msg = "Flagged:\n" + "\n".join(lines)
        _reply_to_self(self_handle, msg, dry_run)
        return msg

    elif action == "personas":
        lines = [f"{k}: {v['name']} - {v['description']}"
                 for k, v in personas.PERSONAS.items()]
        msg = "Available personas:\n" + "\n".join(lines)
        _reply_to_self(self_handle, msg, dry_run)
        return msg

    elif action == "status":
        flagged = config.get_flagged()
        active = sum(1 for e in flagged.values() if e.get("active", True))
        msg = f"SpamSpam running. {active} active conversations."
        _reply_to_self(self_handle, msg, dry_run)
        return msg

    return "Unknown command"


def _reply_to_self(self_handle: str, text: str, dry_run: bool):
    """Send a reply to the self-conversation."""
    if dry_run:
        print(f"  [DRY RUN] Would reply to self: {text}")
    else:
        sender.send_self_message(self_handle, text)
