"""Read-only access to macOS Messages chat.db."""

import os
import plistlib
import re
import sqlite3
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CHAT_DB_PATH = Path.home() / "Library" / "Messages" / "chat.db"
MIRROR_DIR = Path.home() / ".config" / "spamspam" / "db_mirror"
HELPER_APP = Path.home() / ".config" / "spamspam" / "SpamSpamSync.app"
APPLE_EPOCH_OFFSET = 978307200  # seconds between Unix epoch and 2001-01-01


def can_read_db_directly() -> bool:
    """Check if we can read chat.db without the helper."""
    try:
        conn = sqlite3.connect(
            f"file:{CHAT_DB_PATH}?mode=ro", uri=True, timeout=2)
        conn.execute("SELECT 1 FROM message LIMIT 1")
        conn.close()
        return True
    except Exception:
        return False


def create_sync_helper() -> Path:
    """Create a minimal .app bundle that copies chat.db.

    The user grants Full Disk Access to this tiny app (not their terminal).
    It's a background-only app (no Dock icon) that copies the DB and exits.
    """
    app = HELPER_APP
    macos_dir = app / "Contents" / "MacOS"
    macos_dir.mkdir(parents=True, exist_ok=True)
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)

    # Info.plist - marks as background-only (no Dock icon)
    info_plist = {
        "CFBundleIdentifier": "com.spamspam.sync",
        "CFBundleName": "SpamSpamSync",
        "CFBundleExecutable": "sync",
        "CFBundleVersion": "1.0",
        "LSUIElement": True,  # no Dock icon
    }
    with open(app / "Contents" / "Info.plist", "wb") as f:
        plistlib.dump(info_plist, f)

    # The actual sync script
    script = app / "Contents" / "MacOS" / "sync"
    src = CHAT_DB_PATH
    dst = MIRROR_DIR
    script.write_text(f"""#!/bin/bash
cp "{src}" "{dst}/" 2>/dev/null
cp "{src}-wal" "{dst}/" 2>/dev/null
cp "{src}-shm" "{dst}/" 2>/dev/null
exit 0
""")
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    return app


def sync_db() -> Path:
    """Sync chat.db using the helper app. Returns path to the mirror."""
    if not HELPER_APP.exists():
        raise FileNotFoundError(
            "Sync helper not installed. Run: python -m spamspam install-helper"
        )

    result = subprocess.run(
        ["open", "-jgW", str(HELPER_APP)],
        capture_output=True, text=True, timeout=30,
    )

    dest = MIRROR_DIR / "chat.db"
    if not dest.exists():
        raise RuntimeError(
            "Sync helper ran but chat.db was not copied.\n"
            "The helper app likely needs Full Disk Access.\n"
            "Go to: System Settings > Privacy & Security > Full Disk Access\n"
            f"Add: {HELPER_APP}"
        )
    return dest


@dataclass
class Message:
    rowid: int
    text: str | None
    is_from_me: bool
    timestamp: datetime
    service: str  # "iMessage" or "SMS"
    handle: str  # phone number or email


def _apple_ts_to_datetime(nanoseconds: int) -> datetime:
    if nanoseconds == 0:
        return datetime.fromtimestamp(0)
    unix_ts = (nanoseconds / 1e9) + APPLE_EPOCH_OFFSET
    return datetime.fromtimestamp(unix_ts)


def _decode_attributed_body(blob: bytes | None) -> str | None:
    """Extract plain text from NSAttributedString binary blob (macOS Ventura+)."""
    if blob is None:
        return None
    try:
        # The text is stored in a streamtyped NSAttributedString.
        # Look for the content between known markers.
        # Method 1: Find text after "NSString" marker
        idx = blob.find(b"NSString")
        if idx != -1:
            # Skip past "NSString" and length-encoding bytes
            remainder = blob[idx + 8:]
            # The text content follows after some binary prefix bytes.
            # Find the first printable run.
            match = re.search(
                rb"[\x0e-\x1f]([\x20-\x7e\xc0-\xff][\x00-\xff]*?)(?:\x03|\x04|\x06|\x00\x00)",
                remainder,
            )
            if match:
                text = match.group(1).decode("utf-8", errors="replace").strip()
                if text:
                    return text

        # Method 2: Look for NSMutableString pattern
        idx = blob.find(b"NSMutableString")
        if idx != -1:
            remainder = blob[idx + 15:]
            match = re.search(
                rb"[\x0e-\x1f]([\x20-\x7e\xc0-\xff][\x00-\xff]*?)(?:\x03|\x04|\x06|\x00\x00)",
                remainder,
            )
            if match:
                text = match.group(1).decode("utf-8", errors="replace").strip()
                if text:
                    return text

        # Method 3: brute-force - find longest printable UTF-8 run
        runs = re.findall(rb"([\x20-\x7e]{4,})", blob)
        if runs:
            # Filter out known non-content strings
            skip = {b"NSString", b"NSMutableString", b"NSAttributedString",
                    b"NSDictionary", b"NSNumber", b"NSObject", b"NSValue",
                    b"streamtyped"}
            content_runs = [r for r in runs if r not in skip and not r.startswith(b"NS")]
            if content_runs:
                longest = max(content_runs, key=len)
                return longest.decode("utf-8", errors="replace").strip()
    except Exception:
        pass
    return None


def _get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or CHAT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Messages database not found at {path}\n"
            "Make sure you're running on macOS and your terminal has Full Disk Access.\n"
            "System Preferences > Privacy & Security > Full Disk Access"
        )
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _get_message_text(row: sqlite3.Row) -> str | None:
    """Get message text, falling back to attributedBody decoding."""
    text = row["text"]
    if text:
        return text
    return _decode_attributed_body(row["attributedBody"])


def get_recent_messages(handle_id: str, since_rowid: int = 0,
                        limit: int = 50, db_path: Path | None = None) -> list[Message]:
    """Get messages from a specific handle (phone/email) since a given ROWID."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me,
                   m.date, m.service, h.id as handle_identifier
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE h.id = ?
              AND m.ROWID > ?
            ORDER BY m.ROWID ASC
            LIMIT ?
        """, (handle_id, since_rowid, limit))

        messages = []
        for row in cursor:
            text = _get_message_text(row)
            if text is None:
                continue
            messages.append(Message(
                rowid=row["ROWID"],
                text=text,
                is_from_me=bool(row["is_from_me"]),
                timestamp=_apple_ts_to_datetime(row["date"] or 0),
                service=row["service"] or "SMS",
                handle=row["handle_identifier"],
            ))
        return messages
    finally:
        conn.close()


def get_self_messages(self_handle: str, since_rowid: int = 0,
                      limit: int = 20, db_path: Path | None = None) -> list[Message]:
    """Get messages from the user's self-conversation (for command detection)."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT m.ROWID, m.text, m.attributedBody, m.is_from_me,
                   m.date, m.service
            FROM message m
            JOIN chat_message_join cmj ON m.ROWID = cmj.message_id
            JOIN chat c ON cmj.chat_id = c.ROWID
            WHERE c.chat_identifier = ?
              AND m.is_from_me = 1
              AND m.ROWID > ?
            ORDER BY m.ROWID ASC
            LIMIT ?
        """, (self_handle, since_rowid, limit))

        messages = []
        for row in cursor:
            text = _get_message_text(row)
            if text is None:
                continue
            messages.append(Message(
                rowid=row["ROWID"],
                text=text,
                is_from_me=True,
                timestamp=_apple_ts_to_datetime(row["date"] or 0),
                service=row["service"] or "iMessage",
                handle=self_handle,
            ))
        return messages
    finally:
        conn.close()


def get_latest_rowid_for_handle(handle_id: str,
                                db_path: Path | None = None) -> int:
    """Get the most recent message ROWID for a given handle."""
    conn = _get_connection(db_path)
    try:
        row = conn.execute("""
            SELECT MAX(m.ROWID) as max_rowid
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE h.id = ?
        """, (handle_id,)).fetchone()
        return row["max_rowid"] or 0 if row else 0
    finally:
        conn.close()


def detect_service_for_handle(handle_id: str,
                              db_path: Path | None = None) -> str:
    """Detect whether a handle uses iMessage or SMS based on recent messages."""
    conn = _get_connection(db_path)
    try:
        row = conn.execute("""
            SELECT m.service
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE h.id = ?
            ORDER BY m.ROWID DESC
            LIMIT 1
        """, (handle_id,)).fetchone()
        return row["service"] if row and row["service"] else "SMS"
    finally:
        conn.close()


def list_conversations(limit: int = 30,
                       db_path: Path | None = None) -> list[dict]:
    """List recent conversations with message counts."""
    conn = _get_connection(db_path)
    try:
        cursor = conn.execute("""
            SELECT h.id as handle, COUNT(m.ROWID) as msg_count,
                   MAX(m.date) as last_date, m.service
            FROM message m
            JOIN handle h ON m.handle_id = h.ROWID
            WHERE m.date IS NOT NULL
            GROUP BY h.id
            ORDER BY last_date DESC
            LIMIT ?
        """, (limit,))
        results = []
        for row in cursor:
            results.append({
                "handle": row["handle"],
                "message_count": row["msg_count"],
                "last_message": _apple_ts_to_datetime(row["last_date"] or 0),
                "service": row["service"] or "SMS",
            })
        return results
    finally:
        conn.close()
