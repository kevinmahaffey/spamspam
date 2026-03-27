# SpamSpam

AI-powered spam engagement bot for iMessage/SMS on macOS. Automatically responds to spammers with absurd, hilarious personas to waste their time.

## Quick Start

### Option A: Claude Max/Pro (OAuth, no API key needed)

```bash
pip install claude-agent-sdk

# Make sure you're logged into Claude Code (run 'claude' once to authenticate)

python -m spamspam setup +15559990000
python -m spamspam run --oauth
```

### Option B: API Key

```bash
pip install anthropic
export ANTHROPIC_API_KEY=sk-ant-...

python -m spamspam setup +15559990000
python -m spamspam run
```

## Flag Spam from Your iPhone

The easiest way to flag a spammer is by texting yourself:

1. Open the spam conversation on your iPhone
2. Tap the phone number at the top > Copy
3. Open your own conversation (text yourself)
4. Type: `spam +15551234567`

The bot will pick a random persona and start engaging. You'll get a confirmation in your self-chat.

**Remember to mute the spam conversation** (swipe left on the conversation > tap bell icon) so you don't get notifications.

### Self-Text Commands

| Command | What it does |
|---|---|
| `spam +1555...` | Flag with random persona |
| `spam +1555... alien_researcher` | Flag with specific persona |
| `stop +1555...` | Stop engaging |
| `list` | Show flagged numbers |
| `personas` | Show available personas |
| `status` | Bot status |

## CLI Commands

```bash
python -m spamspam setup +15559990000        # Set your phone number
python -m spamspam flag +15551234567         # Flag from terminal
python -m spamspam flag +1555... -p alien_researcher
python -m spamspam unflag +15551234567       # Unflag
python -m spamspam list                      # Show flagged numbers
python -m spamspam personas                  # Show available personas
python -m spamspam log +15551234567          # View conversation
python -m spamspam conversations             # List recent conversations
python -m spamspam run                       # Start bot (30s poll)
python -m spamspam run --interval 60         # Custom poll interval
python -m spamspam run --dry-run             # Test without sending
```

## Personas

| Key | Name | Description |
|---|---|---|
| `confused_grandma` | Ethel | 83yo who thinks you're her grandson Kevin |
| `alien_researcher` | Zyx-7 | Alien studying human commerce |
| `time_traveler` | Chuck | Farmer from 1847, trades livestock |
| `conspiracy_theorist` | Dale | Everything connects to birds/moon/dentists |
| `method_actor` | Reginald | Won't break character as submarine captain |
| `mlm_hun` | Brenda | Aggressively recruits for fictional bee MLM |
| `wrong_number_insistent` | Gary | Insists spammer owes him $47.50 |
| `extremely_literal` | Dr. Pedantic | Takes everything 100% literally |

## macOS Permissions

Your terminal app needs:
- **Full Disk Access** -- to read `~/Library/Messages/chat.db`
- **Automation** for Messages.app -- to send replies via AppleScript

Grant these in: System Settings > Privacy & Security

## How It Works

1. **Polling loop** checks `~/Library/Messages/chat.db` every 30 seconds (read-only)
2. **Self-text commands** are detected in your own conversation thread
3. For flagged numbers, new incoming messages trigger **AI-generated responses** via Claude
4. Responses are sent through **Messages.app** via AppleScript
5. **Random delays** (5-45s) make responses look human
6. **Conversation history** is maintained for coherent (if absurd) continuity
7. State is persisted to `~/.config/spamspam/state.json`
