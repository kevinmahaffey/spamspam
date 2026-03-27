"""CLI interface for SpamSpam."""

import argparse
import sys

from . import config, db, display
from .personas import PERSONAS, list_personas, pick_persona
from .sender import print_mute_instructions


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(
        prog="spamspam",
        description="AI-powered spam engagement bot for iMessage/SMS",
    )
    sub = parser.add_subparsers(dest="command")

    # install-helper
    sub.add_parser("install-helper",
                   help="Create the DB sync helper app (avoids Full Disk Access on terminal)")

    # setup
    setup_p = sub.add_parser("setup", help="Configure your phone number/email")
    setup_p.add_argument("handle", nargs="?",
                         help="Your phone number or iMessage email (e.g. +15559990000)")

    # flag
    flag_p = sub.add_parser("flag", help="Flag a number as spam")
    flag_p.add_argument("number", help="Phone number to flag (e.g. +15551234567)")
    flag_p.add_argument("--persona", "-p", help="Persona to use (see 'personas' command)")

    # unflag
    unflag_p = sub.add_parser("unflag", help="Stop engaging with a number")
    unflag_p.add_argument("number", help="Phone number to unflag")

    # list
    sub.add_parser("list", help="List flagged numbers")

    # personas
    sub.add_parser("personas", help="Show available personas")

    # log
    log_p = sub.add_parser("log", help="View conversation history")
    log_p.add_argument("number", help="Phone number to view")

    # run
    run_p = sub.add_parser("run", help="Start the bot")
    run_p.add_argument("--interval", "-i", type=int, default=30,
                       help="Poll interval in seconds (default: 30)")
    run_p.add_argument("--dry-run", "-n", action="store_true",
                       help="Don't actually send messages")
    run_p.add_argument("--oauth", action="store_true",
                       help="Use Claude Max/Pro OAuth instead of API key "
                            "(requires claude-agent-sdk)")
    run_p.add_argument("--db-path", metavar="PATH",
                       help="Path to a copy of chat.db (bypasses Full Disk Access). "
                            "If omitted, auto-syncs via Finder if direct access fails.")

    # conversations
    sub.add_parser("conversations", help="List recent conversations from Messages")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return

    if args.command == "install-helper":
        _cmd_install_helper()
    elif args.command == "setup":
        _cmd_setup(args)
    elif args.command == "flag":
        _cmd_flag(args)
    elif args.command == "unflag":
        _cmd_unflag(args)
    elif args.command == "list":
        _cmd_list()
    elif args.command == "personas":
        _cmd_personas()
    elif args.command == "log":
        _cmd_log(args)
    elif args.command == "run":
        _cmd_run(args)
    elif args.command == "conversations":
        _cmd_conversations()


def _cmd_install_helper():
    app_path = db.create_sync_helper()
    print(f"Created sync helper at:\n  {app_path}\n")

    if db.can_read_db_directly():
        print("Note: Your terminal already has Full Disk Access, so the helper")
        print("isn't strictly needed. But it's there if you want to revoke FDA later.\n")
        return

    print("Now grant it Full Disk Access:")
    print("  1. Open System Settings > Privacy & Security > Full Disk Access")
    print(f"  2. Click '+' and add: {app_path}")
    print("  3. (Or drag SpamSpamSync.app from Finder into the list)\n")
    print(f"The helper lives at: {app_path}")
    print("It does exactly one thing: copies chat.db to a readable location.")
    print("You can inspect it yourself - it's just a 4-line bash script.\n")

    # Try to open System Settings to the right pane (macOS only)
    import subprocess
    try:
        subprocess.run(
            ["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles"],
            capture_output=True, timeout=5,
        )
    except FileNotFoundError:
        pass  # not on macOS


def _cmd_setup(args):
    handle = args.handle
    if not handle:
        handle = input("Enter your phone number or iMessage email: ").strip()
    if not handle:
        print("No handle provided.")
        return

    config.set_self_handle(handle)
    print(f"Self handle set to: {handle}")

    if not db.can_read_db_directly() and not db.HELPER_APP.exists():
        print("\nNext: install the DB sync helper (avoids granting FDA to your terminal):")
        print("  python -m spamspam install-helper\n")

    print("You can now text yourself commands from your iPhone:")
    print("  spam +15551234567          - flag a spammer")
    print("  spam +15551234567 alien    - flag with specific persona")
    print("  stop +15551234567          - stop engaging")
    print("  list                       - show flagged numbers")
    print("  personas                   - show available personas")


def _cmd_flag(args):
    number = args.number
    persona_key = args.persona

    if persona_key and persona_key not in PERSONAS:
        print(f"Unknown persona '{persona_key}'. Available:")
        for k, name, desc in list_personas():
            print(f"  {k}: {name} - {desc}")
        return

    if persona_key:
        persona = PERSONAS[persona_key]
    else:
        persona_key, persona = pick_persona()

    # Try to detect service and latest message from DB
    try:
        latest_rowid = db.get_latest_rowid_for_handle(number)
        service = db.detect_service_for_handle(number)
    except Exception:
        latest_rowid = 0
        service = "SMS"

    config.flag_number(number, persona_key, service, latest_rowid)
    print(f"Flagged {number} as {persona['name']} ({persona_key}) via {service}")
    print_mute_instructions(number)


def _cmd_unflag(args):
    if config.unflag_number(args.number):
        print(f"Stopped engaging with {args.number}")
    else:
        print(f"{args.number} was not flagged.")


def _cmd_list():
    flagged = config.get_flagged()
    display.print_flagged_list(flagged)


def _cmd_personas():
    print(f"\n{display.BOLD}Available Personas:{display.RESET}\n")
    for key, name, desc in list_personas():
        print(f"  {display.CYAN}{key}{display.RESET}: {name} - {desc}")
    print()


def _cmd_log(args):
    number = args.number
    flagged = config.get_flagged()
    entry = flagged.get(number)

    if not entry:
        print(f"{number} is not flagged. Showing recent messages from DB...\n")
        persona_name = "You"
    else:
        persona_key = entry.get("persona", "unknown")
        persona_name = PERSONAS.get(persona_key, {}).get("name", "Unknown")

    try:
        messages = db.get_recent_messages(number, limit=50)
        display.print_conversation(number, messages, persona_name)
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
    except Exception as e:
        print(f"[ERROR] Could not read messages: {e}")

    # Also show conversation history from state if available
    if entry and entry.get("conversation_history"):
        history = entry["conversation_history"]
        exchanges = len(history) // 2
        print(f"  {display.DIM}({exchanges} exchanges tracked in bot state){display.RESET}\n")


def _cmd_run(args):
    state = config.load_state()
    if not state.get("self_handle"):
        print("[ERROR] No self_handle configured.")
        print("Run: python -m spamspam setup <your-phone-or-email>")
        print("Example: python -m spamspam setup +15559990000")
        return

    from .bot import SpamBot
    bot = SpamBot(poll_interval=args.interval, dry_run=args.dry_run,
                  use_oauth=args.oauth, db_path=args.db_path)
    bot.run()


def _cmd_conversations():
    try:
        convos = db.list_conversations()
        if not convos:
            print("No conversations found.")
            return
        print(f"\n{display.BOLD}Recent Conversations:{display.RESET}\n")
        for c in convos:
            ts = c["last_message"].strftime("%m/%d %I:%M %p")
            flagged = config.get_flagged()
            flag_marker = f" {display.RED}[FLAGGED]{display.RESET}" if c["handle"] in flagged else ""
            print(f"  {c['handle']}: {c['message_count']} msgs, last {ts} ({c['service']}){flag_marker}")
        print()
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
    except Exception as e:
        print(f"[ERROR] Could not list conversations: {e}")
