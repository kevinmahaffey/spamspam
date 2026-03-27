"""Terminal display for viewing conversations."""

from .db import Message


# ANSI color codes
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
DIM = "\033[2m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_conversation(number: str, messages: list[Message], persona_name: str):
    """Pretty-print a conversation in the terminal."""
    print(f"\n{BOLD}{'=' * 55}{RESET}")
    print(f"  {BOLD}Conversation with {number}{RESET} (as {CYAN}{persona_name}{RESET})")
    print(f"{BOLD}{'=' * 55}{RESET}\n")

    for msg in messages:
        timestamp = msg.timestamp.strftime("%m/%d %I:%M %p")
        ts_str = f"{DIM}[{timestamp}]{RESET}"

        if msg.is_from_me:
            print(f"  {ts_str} {GREEN}{persona_name}: {msg.text}{RESET}")
        else:
            print(f"  {ts_str} {RED}Spammer: {msg.text}{RESET}")

    if not messages:
        print(f"  {DIM}(no messages yet){RESET}")
    print()


def print_flagged_list(flagged: dict):
    """Print the list of flagged numbers."""
    if not flagged:
        print("\n  No numbers currently flagged.\n")
        return

    print(f"\n{BOLD}Flagged Conversations:{RESET}\n")
    for number, entry in flagged.items():
        status = f"{GREEN}active{RESET}" if entry.get("active", True) else f"{YELLOW}paused{RESET}"
        persona_key = entry.get("persona", "unknown")
        from .personas import PERSONAS
        name = PERSONAS.get(persona_key, {}).get("name", "?")
        exchanges = len(entry.get("conversation_history", [])) // 2
        service = entry.get("service", "SMS")
        print(f"  {BOLD}{number}{RESET}")
        print(f"    Persona: {CYAN}{name}{RESET} ({persona_key})")
        print(f"    Service: {service} | Exchanges: {exchanges} | Status: {status}")
    print()


def print_bot_status(flagged: dict, poll_interval: int, dry_run: bool):
    """Print bot status banner."""
    active = sum(1 for e in flagged.values() if e.get("active", True))
    mode = f"{YELLOW}DRY RUN{RESET}" if dry_run else f"{GREEN}LIVE{RESET}"

    print(f"\n{BOLD}{'=' * 55}{RESET}")
    print(f"  {BOLD}SpamSpam Bot{RESET} [{mode}]")
    print(f"  Polling every {poll_interval}s | {active} active conversations")
    print(f"{BOLD}{'=' * 55}{RESET}\n")
