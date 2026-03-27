"""Send messages via macOS Messages.app using AppleScript."""

import subprocess


def send_message(recipient: str, text: str, service: str = "SMS") -> bool:
    """Send a message via Messages.app using osascript.

    Args:
        recipient: Phone number or email address
        text: Message content
        service: "SMS" or "iMessage"

    Returns:
        True if the message was sent successfully
    """
    # Escape for AppleScript string literal
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')

    # Build the AppleScript command
    # Use the service name that Messages.app recognizes
    if service == "iMessage":
        service_type = 'id "com.apple.iMessage"'
    else:
        service_type = 'id "com.apple.MMS"'

    script = (
        f'tell application "Messages"\n'
        f'  set targetService to 1st service whose {service_type}\n'
        f'  set targetBuddy to buddy "{recipient}" of targetService\n'
        f'  send "{escaped}" to targetBuddy\n'
        f'end tell'
    )

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            # Try simpler approach as fallback
            simple_script = (
                f'tell application "Messages" to send "{escaped}" '
                f'to buddy "{recipient}" of service "{service}"'
            )
            result = subprocess.run(
                ["osascript", "-e", simple_script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except FileNotFoundError:
        print("[ERROR] osascript not found. Are you running on macOS?")
        return False


def send_self_message(self_handle: str, text: str) -> bool:
    """Send a message to the user's own conversation (for command responses)."""
    return send_message(self_handle, text, service="iMessage")


def print_mute_instructions(number: str):
    """Print instructions for muting a conversation."""
    print(f"\n  To silence notifications for {number}:")
    print("  1. Open Messages.app")
    print(f"  2. Find the conversation with {number}")
    print("  3. Right-click (or Control-click) the conversation")
    print('  4. Select "Hide Alerts"')
    print("  (On iPhone: swipe left on the conversation > tap bell icon)\n")
