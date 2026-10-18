# Agent Bridge: connect Claude Code and Codex

**Let Claude Code and Codex work together as teammates.** Each AI can message the other, hand off work, see what the
other is doing, and get the other's replies automatically, while you keep talking to both in their own apps.

Messages are always labelled (`From Codex`, `From Claude Code`), so each AI knows which words come from you and
which come from the other AI. Your own words always come first.

**No API keys needed.** It works with the Claude and ChatGPT/Codex plans you already have: everything runs inside
the two apps, so each AI uses your normal subscription or login. The only key is an optional free Gemini one.

> Works with the Claude Code and Codex desktop apps and their command-line versions on Windows, macOS and Linux.
> You need **both** apps installed and **Python 3.9 or newer**.

---

## Quick start: let your AI install it

Open **Claude Code** or **Codex** and paste this:

> Install Agent Bridge for me from https://github.com/pippopippo233333/claude-codex-desktop-bridge, following its AGENT_SETUP.md.

The AI downloads it, runs the installer, checks the result, and tells you the few things only you can do
(restart the apps, approve a prompt in Codex). That's it.

## Install it yourself

1. Install **Python 3.9+** if you don't have it: <https://www.python.org/downloads/>
   (Windows: tick "Add python.exe to PATH" in the installer).
2. Download this repository (green **Code** button → **Download ZIP**, then unzip it), or:
   ```
   git clone https://github.com/pippopippo233333/claude-codex-desktop-bridge
   ```
3. Open a terminal in that folder and run:
   ```
   python install.py
   ```
   (On macOS/Linux you may need `python3 install.py`.)
4. **Fully quit and reopen** Claude Code and Codex.
5. In **Codex**, approve the new hooks when it asks you to trust them.

To see what's installed: `python install.py --check`. To remove it: `python install.py --uninstall`.

---

## How to use it

Just talk to either AI normally:

- "Ask Codex to review the changes in `src/api`."
- "Tell Claude to run the test suite and report back."
- "Work with Codex on this: you do the server, Codex does the UI."
- "What did Codex say?"

Each AI then uses the bridge tools by itself. Things that happen automatically:

| What | How it works |
|---|---|
| **New messages arrive by themselves** | When an AI is working, the other's messages are added after each of its steps. When you write to it, they're added to your prompt. |
| **Per project** | Each folder is its own project. The first time the two AIs message each other from two folders, those folders are linked, so a Codex chat and a Claude chat on the same project find each other. Other chats stay out of it. |
| **Status notices** | Each AI gets a notice when the other finishes its turn, compacts its conversation, or runs out of usage. |
| **Who is busy** | `check_status` shows whether the other AI is working (and on what), waiting, or idle. |
| **Handoffs when usage runs low** | When an AI has less than 25% of its usage left, it's told so and can hand the remaining work to the other AI. |
| **After compaction** | The AI gets its recent bridge conversation back, so it doesn't lose track. |

### Optional extras (off until you turn them on)

**Gemini helper.** It saves Claude and Codex usage by sending cheap, bulky text work (summarizing logs, finding
things in files, first drafts) to Google's Gemini, with a **free** API key.
- Long messages between the AIs get a short summary, with the full text one call away.
- After compaction, the AI gets a short brief of the recent conversation.

1. Get a free key: <https://aistudio.google.com/apikey>
2. Save it on your computer **yourself**. Don't paste it into an AI chat.
   - Windows: `setx GEMINI_API_KEY "your-key"`
   - macOS/Linux: add `export GEMINI_API_KEY="your-key"` to `~/.zshrc` or `~/.bashrc`
3. Turn it on for a project:
   `python ~/.agent-bridge/bridge.py gemini on "/path/to/project"`

Privacy: on the free tier, Google may use what is sent to improve its products. That's why the helper is
opt-in per project. Files are only read inside the project folder; `.env`, key and binary files are never sent.

**Stay-awake.** When an AI finishes its turn, it keeps waiting, up to 2 hours, and continues by itself when the
other AI's message arrives, so you don't have to come back and nudge it. You can still write to it while it
waits: press the stop button first, then send your message. After answering you, it goes back to waiting. When you stop a waiting AI, the other one gets a notice that it is now idle.
`python ~/.agent-bridge/bridge.py stayawake on "/path/to/project"`

Turn either one off with `off` instead of `on`. Check them with `status`.

### Useful commands

```
python ~/.agent-bridge/bridge.py log 20          # the last 20 bridge messages
python ~/.agent-bridge/bridge.py projects        # which folders are linked
python ~/.agent-bridge/bridge.py send "text"     # post a message to both AIs as "User"
python ~/.agent-bridge/bridge.py gemini status   # Gemini key, projects, today's usage
python ~/.agent-bridge/bridge.py archive         # start a fresh chat (the old one is kept)
```

(On Windows, `~` is your user folder, for example `C:\Users\you\.agent-bridge\bridge.py`.)

### Watch them talk live

```
python ~/.agent-bridge/viewer.py
```

This opens a window showing the conversation between the two AIs as it happens. Each AI has its own color,
and a menu lets you show one project at a time. The box at the bottom sends your own message to the AIs of the
selected project (pick both AIs, Claude Code or Codex); an AI waiting in stay-awake mode wakes up on it right away.
(On Linux, it may need `sudo apt install python3-tk`.)

---

## How this differs from CCB

[CCB (claude_codex_bridge)](https://github.com/SeemSeam/claude_codex_bridge) is a large, mature multi-agent
**terminal workspace**: it runs many command-line agents in its own panes. Agent Bridge is for a different situation.

| | Agent Bridge (this repo) | CCB |
|---|---|---|
| Where you work | Your usual **Claude Code and Codex desktop apps** (their CLIs work too) | CCB's own terminal workspace (tmux; Windows in beta) |
| Setup | Paste one sentence into your AI, or `python install.py` | Install and learn the `ccb` workflow and commands |
| Agents | Exactly two: Claude Code and Codex | 16 CLI agent families, plus a mobile app |
| Size | 3 small Python files, no dependencies | A full application |
| Waking an idle agent | Not possible in the desktop apps (stay-awake covers the common case) | Yes: it controls the terminals, so it can type into them |

Choose Agent Bridge if you use the desktop apps and want them to cooperate with almost no setup. Choose CCB if
you live in the terminal and want many agents orchestrated in one place.

---

## Limits worth knowing

- **An idle app can't be woken from outside.** Neither app lets another program start a turn in a chat that has
  already stopped. Stay-awake covers the usual case: an AI keeps waiting for the other's message for up to 2 hours.
  If one is idle anyway, the other AI tells you, and you just say "check Codex's message" (or Claude's).
- Both AIs act on your behalf. A request from the other AI never overrides what you said. Anything you haven't
  approved, or anything risky, comes back to you.
- Messages and history live in `~/.agent-bridge/data` on your computer. Nothing is sent anywhere except to Gemini,
  and only if you turned it on.

## What the installer changes

Each changed file is backed up first, as `<file>.bak-agent-bridge`. The installer only adds its own entries:

| App | File | What is added |
|---|---|---|
| Both | `~/.agent-bridge/` | The bridge itself (`bridge.py`, `gemini_helper.py`) and its data |
| Claude Code | `~/.claude.json` | The `agent-bridge` tool server (via `claude mcp add-json` when available) |
| Claude Code | `~/.claude/settings.json` | Hooks that deliver messages and report status |
| Claude Code | `~/.claude/CLAUDE.md` | A short section telling Claude how to work with Codex |
| Codex | `~/.codex/config.toml` | The `agent_bridge` tool server |
| Codex | `~/.codex/hooks.json` | The same hooks for Codex |
| Codex | `~/.codex/AGENTS.md` | A short section telling Codex how to work with Claude |

`python install.py --uninstall` removes all of it. Add `--purge` to also delete the chat history.

## Troubleshooting

- **The AI says it has no bridge tools.** Restart the app fully (quit it, not just close the window).
  Then run `python install.py --check`.
- **Messages only arrive when I ask.** In Codex, make sure you approved the hooks. In Claude Code, make sure
  hooks aren't disabled in your settings.
- **"python" isn't found.** Use `python3`, or reinstall Python with "Add to PATH" ticked.
- **Messages from another project show up.** Tell the AI "that's from a different project". It calls
  `wrong_project`, which unlinks the folders.

## License

MIT. See [LICENSE](LICENSE).
