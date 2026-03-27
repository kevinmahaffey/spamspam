"""Main polling loop orchestrator."""

import random
import sqlite3
import threading
import time
from datetime import datetime

from . import config, db, commands, display
from .ai import ResponseGenerator
from .personas import PERSONAS
from .sender import send_message


class SpamBot:
    def __init__(self, poll_interval: int = 30, dry_run: bool = False):
        self.poll_interval = poll_interval
        self.dry_run = dry_run
        self.ai = ResponseGenerator()

    def run(self):
        """Main polling loop."""
        state = config.load_state()
        self_handle = state.get("self_handle")

        if not self_handle:
            print("[ERROR] No self_handle configured.")
            print("Run: python -m spamspam setup")
            return

        display.print_bot_status(state.get("flagged", {}), self.poll_interval, self.dry_run)

        if self_handle:
            print(f"  Monitoring self-conversation: {self_handle}")
            print(f"  Text yourself commands like: spam +15551234567\n")

        try:
            while True:
                self._poll_cycle()
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            print("\nShutting down SpamSpam.")

    def _poll_cycle(self):
        """One poll cycle: check commands, then process conversations."""
        state = config.load_state()
        self_handle = state.get("self_handle")

        # Phase 1: Check for self-text commands
        if self_handle:
            self._process_commands(state, self_handle)

        # Phase 2: Process flagged conversations
        # Re-read state since commands may have modified it
        state = config.load_state()
        flagged = state.get("flagged", {})

        if not flagged:
            return

        # Process each flagged number in a thread for parallel delays
        threads = []
        for number, entry in flagged.items():
            if not entry.get("active", True):
                continue
            t = threading.Thread(
                target=self._process_conversation,
                args=(number, entry),
                daemon=True,
            )
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=120)

    def _process_commands(self, state: dict, self_handle: str):
        """Scan self-conversation for new commands."""
        last_rowid = state.get("last_command_rowid", 0)

        try:
            messages = db.get_self_messages(self_handle, since_rowid=last_rowid)
        except (FileNotFoundError, sqlite3.OperationalError) as e:
            print(f"[WARN] Could not read messages DB: {e}")
            return

        if not messages:
            return

        for msg in messages:
            cmd = commands.parse_command(msg.text)
            if cmd:
                ts = msg.timestamp.strftime("%H:%M:%S")
                print(f"[{ts}] Command received: {msg.text}")
                result = commands.execute_command(cmd, self_handle, self.dry_run)
                print(f"  -> {result}")

        # Update cursor to latest message
        state["last_command_rowid"] = messages[-1].rowid
        config.save_state(state)

    def _process_conversation(self, number: str, entry: dict):
        """Handle one flagged conversation - check for new messages and respond."""
        last_id = entry.get("last_reply_message_id", 0)

        try:
            messages = db.get_recent_messages(number, since_rowid=last_id)
        except (FileNotFoundError, sqlite3.OperationalError) as e:
            print(f"[WARN] Could not read messages for {number}: {e}")
            return

        # Filter to only incoming messages (from the spammer)
        new_incoming = [m for m in messages if not m.is_from_me]
        if not new_incoming:
            return

        latest = new_incoming[-1]
        incoming_text = latest.text or "[attachment]"

        # Human-like delay
        delay = random.randint(5, 45)
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] New message from {number}: {incoming_text[:80]}")
        print(f"  Waiting {delay}s before responding...")

        if not self.dry_run:
            time.sleep(delay)

        # Get persona
        persona_key = entry.get("persona", "confused_grandma")
        persona = PERSONAS.get(persona_key)
        if not persona:
            print(f"[ERROR] Unknown persona {persona_key} for {number}")
            return

        # Build conversation history
        history = entry.get("conversation_history", [])

        # Generate AI response
        try:
            reply = self.ai.generate_reply(persona, history, incoming_text)
        except Exception as e:
            print(f"[ERROR] AI generation failed for {number}: {e}")
            return

        ts = datetime.now().strftime("%H:%M:%S")

        if self.dry_run:
            print(f"[{ts}] [DRY RUN] Would send to {number} as {persona['name']}: {reply}")
        else:
            service = entry.get("service", "SMS")
            success = send_message(number, reply, service)
            if success:
                print(f"[{ts}] Sent to {number} as {persona['name']}: {reply}")
            else:
                print(f"[{ts}] [ERROR] Failed to send to {number}")
                return

        # Update state
        history.append({"role": "user", "content": incoming_text})
        history.append({"role": "assistant", "content": reply})

        # Cap history at 40 messages (20 exchanges)
        if len(history) > 40:
            history = history[-40:]

        # Re-read and update state atomically
        state = config.load_state()
        if number in state["flagged"]:
            state["flagged"][number]["last_reply_message_id"] = latest.rowid
            state["flagged"][number]["conversation_history"] = history
            config.save_state(state)
