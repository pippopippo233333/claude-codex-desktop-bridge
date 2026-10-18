"""Agent Bridge live viewer: watch the conversation between Claude Code and Codex as it happens.

  python ~/.agent-bridge/viewer.py

Pick a project in the menu to see only its messages. The box at the bottom sends your own message to the
AIs of that project (labelled "From User"); with "All projects" selected it goes to every project.
Uses tkinter, which comes with Python (on Linux you may need: sudo apt install python3-tk).
"""
import json
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk

DATA_DIR = Path(os.environ.get("AGENT_BRIDGE_DIR") or Path(__file__).resolve().parent / "data")
CHAT_FILE = DATA_DIR / "chat.jsonl"
LINKS_FILE = DATA_DIR / "links.json"   # projects (linked folders) of the bridge
POLL_MS = 300          # how often to check the chat file
LINKS_POLL_MS = 2000   # how often to re-check the linked projects
ALL_PROJECTS = "All projects"
EVERYWHERE = "*"       # messages sent to every project (e.g. by the user from the command line)

DISPLAY = {"codex": "Codex", "claude": "Claude Code", "user": "User"}
COLORS = {
    "codex":  "#4FC3F7",  # light blue
    "claude": "#FFB74D",  # orange
    "user":   "#81C784",  # green
    "meta":   "#9E9E9E",  # grey (timestamps etc.)
    "bg":     "#1E1E1E",
    "fg":     "#E0E0E0",
}
# one color per project (stripe on the left + label)
PROJECT_PALETTE = ["#BA68C8", "#4DB6AC", "#F06292", "#AED581", "#7986CB",
                   "#FFD54F", "#4DD0E1", "#FF8A65", "#90A4AE", "#DCE775"]
RECIPIENTS = {"Both AIs": "all", "Claude Code": "claude", "Codex": "codex"}


def post_as_user(text, to, room, folder):
    """Post a message as the user through bridge.py (it sits next to this file, or next to the data folder)."""
    for here in (Path(__file__).resolve().parent, DATA_DIR.parent):
        if (here / "bridge.py").exists():
            if str(here) not in sys.path:
                sys.path.insert(0, str(here))
            break
    import bridge
    return bridge.post("user", text, to=to, room=room, folder=folder)


def display(name):
    return DISPLAY.get(name, name)


def room_key(folder):
    """The same folder key bridge.py uses."""
    if not folder:
        return ""
    return os.path.normcase(os.path.normpath(str(folder))).rstrip("\\/")


def msg_room(msg):
    return msg.get("room") or room_key(msg.get("folder"))


class ChatViewer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agent Bridge - live chat")
        self.geometry("900x650")
        self.configure(bg=COLORS["bg"])

        self.file = None
        self.partial = ""
        self.last_size = 0
        self.autoscroll = tk.BooleanVar(value=True)

        self.messages = []          # every message read (to redraw when the filter changes)
        self.hidden_upto = 0        # "Clear" hides messages up to this id
        self.groups = []            # groups of linked folders (from links.json)
        self.links_mtime = None
        self.folder_case = {}       # folder key -> original path (for names)
        self.project_colors = {}    # project key -> color
        self.name_to_key = {}       # name in the menu -> project key
        self.selected = None        # key of the filtered project (None = all)

        self._build_ui()
        self._load_links()
        self._open_file()
        self._initial_load()
        self.after(POLL_MS, self._poll)
        self.after(LINKS_POLL_MS, self._poll_links)

    # ------------------------------------------------------------- UI
    def _build_ui(self):
        top = tk.Frame(self, bg=COLORS["bg"])
        top.pack(fill="x", padx=10, pady=(10, 4))

        tk.Label(top, text="Agent Bridge", fg="#FFFFFF", bg=COLORS["bg"],
                 font=("Segoe UI", 13, "bold")).pack(side="left")

        tk.Label(top, text="   Project:", fg=COLORS["meta"], bg=COLORS["bg"],
                 font=("Segoe UI", 9)).pack(side="left")
        self.project_var = tk.StringVar(value=ALL_PROJECTS)
        self.project_box = ttk.Combobox(top, textvariable=self.project_var, state="readonly",
                                        width=34, values=[ALL_PROJECTS])
        self.project_box.pack(side="left", padx=(6, 0))
        self.project_box.bind("<<ComboboxSelected>>", self._on_project_selected)

        tk.Checkbutton(top, text="Auto-scroll", variable=self.autoscroll,
                       fg=COLORS["fg"], bg=COLORS["bg"],
                       selectcolor=COLORS["bg"], activebackground=COLORS["bg"],
                       activeforeground=COLORS["fg"], font=("Segoe UI", 9)
                       ).pack(side="right")

        tk.Button(top, text="Clear", command=self._clear,
                  bg="#333", fg=COLORS["fg"], relief="flat", padx=10
                  ).pack(side="right", padx=(0, 8))

        body = tk.Frame(self, bg=COLORS["bg"])
        body.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        mono = tkfont.Font(family="Consolas", size=10)
        self.text = tk.Text(body, wrap="word", bg="#111", fg=COLORS["fg"],
                            insertbackground=COLORS["fg"], font=mono,
                            relief="flat", padx=12, pady=10,
                            state="disabled", cursor="arrow")
        self.text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(body, command=self.text.yview, width=12,
                          bg="#333", troughcolor=COLORS["bg"],
                          activebackground="#555", relief="flat")
        sb.pack(side="right", fill="y")
        self.text.config(yscrollcommand=sb.set)

        for name, color in COLORS.items():
            if name in ("bg", "fg", "meta"):
                continue
            self.text.tag_configure(f"from_{name}", foreground=color,
                                    font=("Consolas", 10, "bold"))
        self.text.tag_configure("meta", foreground=COLORS["meta"])
        self.text.tag_configure("body", foreground=COLORS["fg"],
                                lmargin1=20, lmargin2=20, spacing1=2, spacing3=8)
        self.text.tag_configure("sep", foreground="#333")
        self.text.tag_configure("status", foreground=COLORS["meta"],
                                font=("Consolas", 9, "italic"))

        # send box: your own message to the AIs of the selected project
        compose = tk.Frame(self, bg=COLORS["bg"])
        compose.pack(side="bottom", fill="x", padx=10, pady=(0, 4))
        self.entry = tk.Text(compose, height=3, wrap="word", bg="#111", fg=COLORS["fg"],
                             insertbackground=COLORS["fg"], font=("Consolas", 10),
                             relief="flat", padx=8, pady=6)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", self._on_enter)
        side = tk.Frame(compose, bg=COLORS["bg"])
        side.pack(side="right", padx=(8, 0))
        self.to_var = tk.StringVar(value="Both AIs")
        ttk.Combobox(side, textvariable=self.to_var, state="readonly", width=12,
                     values=list(RECIPIENTS)).pack(fill="x")
        tk.Button(side, text="Send", command=self._send, bg="#2E7D32", fg="#FFFFFF",
                  relief="flat", padx=10).pack(fill="x", pady=(4, 0))
        self.status = tk.Label(self, text="Listening…  (Enter sends, Shift+Enter adds a new line)", anchor="w",
                               fg=COLORS["meta"], bg=COLORS["bg"],
                               font=("Segoe UI", 9))
        self.status.pack(side="bottom", fill="x", padx=12, pady=(0, 8))
        body.pack_forget()
        body.pack(fill="both", expand=True, padx=10, pady=(0, 6))

    def _on_enter(self, event):
        if event.state & 0x1:       # Shift+Enter: new line
            return None
        self._send()
        return "break"

    def _send(self):
        text = self.entry.get("1.0", "end").strip()
        if not text:
            return
        to = RECIPIENTS.get(self.to_var.get(), "all")
        room = self.selected if self.selected is not None else EVERYWHERE
        where = "every project" if room == EVERYWHERE else self._project_name(room)
        try:
            folder = "every project" if room == EVERYWHERE else self.folder_case.get(room, room)
            msg = post_as_user(text, to, room, folder)
        except Exception as e:      # noqa: BLE001 - show any failure in the window
            self.status.config(text=f"Not sent: {e}")
            return
        self.entry.delete("1.0", "end")
        self.status.config(text=f"Sent #{msg['id']} to {self.to_var.get()} in {where}.")

    # ------------------------------------------------------ projects
    def _load_links(self):
        """Re-read links.json if it changed; True if the groups changed."""
        try:
            mtime = LINKS_FILE.stat().st_mtime_ns
        except OSError:
            mtime = None
        if mtime == self.links_mtime:
            return False
        self.links_mtime = mtime
        try:
            data = json.loads(LINKS_FILE.read_text(encoding="utf-8"))
            self.groups = [set(g.get("rooms", [])) for g in data.get("groups", [])]
        except (OSError, ValueError):
            self.groups = []
        return True

    def _project_rooms(self, key):
        for g in self.groups:
            if key in g:
                return g
        return {key}

    def _project_key(self, room):
        """Stable key of a folder's project: the 'smallest' folder of its group."""
        if room == EVERYWHERE:
            return EVERYWHERE
        return min(self._project_rooms(room))   # unlinked folder: a project of its own

    def _project_name(self, key):
        if key == EVERYWHERE:
            return "everyone"
        rooms = sorted(self._project_rooms(key))
        # prefer the project's real folder over Codex's dated chat folders (Documents/Codex/...)
        real = [r for r in rooms if "documents" + os.sep + "codex" + os.sep not in (r + os.sep).lower()]
        room = (real or rooms)[0]
        return Path(self.folder_case.get(room, room)).name or room

    def _project_tag(self, key):
        if key not in self.project_colors:
            self.project_colors[key] = PROJECT_PALETTE[len(self.project_colors) % len(PROJECT_PALETTE)]
        color = self.project_colors[key]
        tag = f"project_{color}"
        self.text.tag_configure(tag, foreground=color, font=("Consolas", 10, "bold"))
        return tag

    def _refresh_menu(self):
        """Update the project menu (duplicate names get a number)."""
        keys, seen = [], set()
        for m in self.messages:
            k = self._project_key(msg_room(m))
            if k != EVERYWHERE and k not in seen:
                seen.add(k)
                keys.append(k)
        self.name_to_key, counts = {}, {}
        for k in keys:
            name = self._project_name(k)
            counts[name] = counts.get(name, 0) + 1
            if counts[name] > 1:
                name = f"{name} ({counts[name]})"
            self.name_to_key[name] = k
        self.project_box["values"] = [ALL_PROJECTS] + list(self.name_to_key)
        # keep the selection even if the project's key changed (folders were linked)
        if self.selected is not None:
            for name, k in self.name_to_key.items():
                if self.selected in self._project_rooms(k):
                    self.selected = k
                    self.project_var.set(name)
                    return
            self.selected = None
            self.project_var.set(ALL_PROJECTS)

    def _on_project_selected(self, _event=None):
        name = self.project_var.get()
        self.selected = None if name == ALL_PROJECTS else self.name_to_key.get(name)
        self._rerender()

    def _poll_links(self):
        try:
            if self._load_links():
                self._refresh_menu()
                self._rerender()
        finally:
            self.after(LINKS_POLL_MS, self._poll_links)

    # ------------------------------------------------------ file handling
    def _open_file(self):
        if not CHAT_FILE.exists():
            self.status.config(text=f"Waiting for {CHAT_FILE} to be created…")
            self.file = None
            return False
        try:
            self.file = open(CHAT_FILE, "r", encoding="utf-8", errors="replace")
            self.last_size = os.path.getsize(CHAT_FILE)
        except OSError as e:
            self.status.config(text=f"Can't open the chat file: {e}")
            self.file = None
            return False
        self.status.config(text="Listening…")
        return True

    def _initial_load(self):
        """Read the whole history and show it."""
        if not self.file:
            return
        self.file.seek(0)
        content = self.file.read()
        self.partial = ""
        self.messages = []
        self.hidden_upto = 0
        lines = content.split("\n")
        # the last line may be half-written (no final newline)
        if content and not content.endswith("\n"):
            self.partial = lines.pop()
        elif lines and lines[-1] == "":
            lines.pop()
        for line in lines:
            msg = self._parse(line)
            if msg:
                self._remember(msg)
        self._refresh_menu()
        self._rerender()

    def _poll(self):
        try:
            if not self.file:
                if self._open_file():
                    self._initial_load()
                return

            # the chat was archived or truncated: start over
            try:
                size = os.path.getsize(CHAT_FILE)
                if size < self.file.tell():
                    self.file.close()
                    self._open_file()
                    self.partial = ""
                    self.last_size = 0
                    self._initial_load()
                    return
            except OSError:
                pass

            new = False
            while True:
                line = self.file.readline()
                if not line:
                    break
                if not line.endswith("\n"):
                    self.partial += line    # half-written line: keep it for later
                    break
                if self.partial:
                    line = self.partial + line
                    self.partial = ""
                msg = self._parse(line)
                if msg:
                    self._remember(msg)
                    self._render(msg)
                    new = True
            if new:
                # a new message may have linked new folders
                if self._load_links():
                    self._refresh_menu()
                    self._rerender()
                else:
                    self._refresh_menu()
        finally:
            self.after(POLL_MS, self._poll)

    @staticmethod
    def _parse(line):
        line = line.strip()
        if not line:
            return None
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _remember(self, msg):
        self.messages.append(msg)
        if msg.get("folder"):
            self.folder_case.setdefault(room_key(msg["folder"]), msg["folder"])

    # ------------------------------------------------------ rendering
    def _visible(self, msg):
        if msg.get("id", 0) <= self.hidden_upto:
            return False
        if self.selected is None:
            return True
        key = self._project_key(msg_room(msg))
        return key == EVERYWHERE or key == self.selected

    def _rerender(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")
        for msg in self.messages:
            self._render(msg, update_status=False)
        if self.autoscroll.get():
            self.text.see("end")

    def _render(self, msg, update_status=True):
        if not self._visible(msg):
            return
        self.text.config(state="normal")

        sender = msg.get("from", "?")
        where = f" (working in {msg['folder']})" if msg.get("folder") else ""

        # colored stripe + project name (the name only in "All projects")
        key = self._project_key(msg_room(msg))
        ptag = self._project_tag(key)
        self.text.insert("end", "▌ ", (ptag,))
        if self.selected is None:
            self.text.insert("end", f"[{self._project_name(key)}] ", (ptag,))

        self.text.insert("end", f"[#{msg.get('id', '?')}] {msg.get('time', '')}  ", ("meta",))
        if msg.get("kind") == "status":
            # status notice (finished its turn, compacting...): one grey line
            self.text.insert("end", f"● {display(sender)}", (f"from_{sender}",))
            self.text.insert("end", f" {msg.get('text', '')}\n\n", ("status",))
            self.text.config(state="disabled")
            if update_status:
                if self.autoscroll.get():
                    self.text.see("end")
                self.status.config(text=f"Status: {display(sender)}  •  {msg.get('time', '')}")
            return
        self.text.insert("end", f"From {display(sender)}", (f"from_{sender}",))
        extra = "  [the other AI got a Gemini summary of this]" if msg.get("summary") else ""
        self.text.insert("end", f"{where}{extra}\n", ("meta",))
        self.text.insert("end", msg.get("text", "") + "\n\n", ("body",))

        self.text.config(state="disabled")

        if update_status:
            if self.autoscroll.get():
                self.text.see("end")
            self.status.config(text=f"Last message: #{msg.get('id', '?')} from {display(sender)}  •  "
                                    f"{msg.get('time', '')}")

    def _clear(self):
        # hide the messages shown so far (they stay hidden when switching projects)
        if self.messages:
            self.hidden_upto = self.messages[-1].get("id", 0)
        self.text.config(state="normal")
        self.text.delete("1.0", "end")
        self.text.config(state="disabled")


if __name__ == "__main__":
    ChatViewer().mainloop()
