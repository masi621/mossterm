from __future__ import annotations

import os
import queue
import shlex
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

APP_NAME = "MOSS Terminal"
HISTORY_FILE = Path.home() / ".local/share/moss-terminal/history.txt"

THEMES = {
    "Matrix": {
        "bg": "#08120a",
        "fg": "#7CFF8A",
        "accent": "#2BEA5F",
        "input_bg": "#0f1b10",
    },
    "Amber": {
        "bg": "#161108",
        "fg": "#FFCC66",
        "accent": "#FFAA33",
        "input_bg": "#23190a",
    },
    "Ice": {
        "bg": "#08141a",
        "fg": "#A9E7FF",
        "accent": "#58C7F3",
        "input_bg": "#0d1c23",
    },
}


class TerminalApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("980x620")
        self.cwd = Path.home()
        self.history: list[str] = []
        self.history_index: int | None = None
        self.font_size = 12
        self.theme_name = tk.StringVar(value="Matrix")
        self.output_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.command_running = False

        self._load_history()
        self._build_ui()
        self.apply_theme()
        self.print_banner()
        self.refresh_prompt()
        self.root.after(100, self._drain_queue)

    def _build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(self.root, padding=(10, 10, 10, 6))
        toolbar.grid(row=0, column=0, sticky="ew")

        ttk.Button(toolbar, text="Clear", command=self.clear_output).pack(side="left")
        ttk.Button(toolbar, text="Copy", command=self.copy_output).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Home", command=self.go_home).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Pwd", command=lambda: self.run_command("pwd")).pack(side="left", padx=(6, 0))

        ttk.Label(toolbar, text="Theme:").pack(side="left", padx=(16, 6))
        theme_box = ttk.Combobox(
            toolbar,
            textvariable=self.theme_name,
            values=list(THEMES.keys()),
            width=10,
            state="readonly",
        )
        theme_box.pack(side="left")
        theme_box.bind("<<ComboboxSelected>>", lambda _e: self.apply_theme())

        ttk.Button(toolbar, text="A-", command=lambda: self.adjust_font(-1)).pack(side="left", padx=(16, 0))
        ttk.Button(toolbar, text="A+", command=lambda: self.adjust_font(1)).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="About", command=self.show_about).pack(side="right")

        body = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.output = tk.Text(
            body,
            wrap="word",
            undo=False,
            padx=10,
            pady=10,
            insertwidth=0,
            relief="flat",
        )
        self.output.grid(row=0, column=0, sticky="nsew")
        self.output.configure(state="disabled")

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.output.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.output.configure(yscrollcommand=scrollbar.set)

        prompt_bar = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        prompt_bar.grid(row=2, column=0, sticky="ew")
        prompt_bar.columnconfigure(1, weight=1)

        self.prompt_var = tk.StringVar(value="$")
        self.prompt_label = ttk.Label(prompt_bar, textvariable=self.prompt_var)
        self.prompt_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.entry = ttk.Entry(prompt_bar)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.entry.bind("<Return>", self.on_enter)
        self.entry.bind("<Up>", self.on_history_up)
        self.entry.bind("<Down>", self.on_history_down)
        self.entry.focus_set()

        ttk.Button(prompt_bar, text="Run", command=lambda: self.run_command(self.entry.get())).grid(
            row=0, column=2, sticky="e", padx=(8, 0)
        )

    def print_banner(self) -> None:
        self.append_output(
            "MOSS Terminal\n"
            "A simple terminal-style app for DebianMOSS\n"
            "Type 'help' to see built-in commands.\n\n",
            tag="accent",
        )

    def refresh_prompt(self) -> None:
        display = str(self.cwd).replace(str(Path.home()), "~", 1)
        self.prompt_var.set(f"{display} $")
        self.root.title(f"{APP_NAME} — {display}")

    def append_output(self, text: str, tag: str = "normal") -> None:
        self.output.configure(state="normal")
        self.output.insert("end", text, (tag,))
        self.output.configure(state="disabled")
        self.output.see("end")

    def clear_output(self) -> None:
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def copy_output(self) -> None:
        content = self.output.get("1.0", "end-1c")
        self.root.clipboard_clear()
        self.root.clipboard_append(content)

    def go_home(self) -> None:
        self.cwd = Path.home()
        self.refresh_prompt()
        self.append_output(f"Changed directory to {self.cwd}\n")

    def show_about(self) -> None:
        messagebox.showinfo(
            APP_NAME,
            "A lightweight terminal-style app built with Python and Tkinter.\n\n"
            "Good for simple commands and demos.\n"
            "Not a full terminal emulator.",
        )

    def adjust_font(self, delta: int) -> None:
        self.font_size = max(9, min(28, self.font_size + delta))
        self.apply_theme()

    def apply_theme(self) -> None:
        theme = THEMES[self.theme_name.get()]
        self.output.configure(
            bg=theme["bg"],
            fg=theme["fg"],
            selectbackground=theme["accent"],
            selectforeground="#000000",
            font=("DejaVu Sans Mono", self.font_size),
        )
        self.output.tag_configure("normal", foreground=theme["fg"], background=theme["bg"])
        self.output.tag_configure("accent", foreground=theme["accent"], background=theme["bg"])
        self.output.tag_configure("error", foreground="#ff7a7a", background=theme["bg"])
        style = ttk.Style()
        style.theme_use(style.theme_use())
        self.root.configure(bg=theme["bg"])

    def on_enter(self, _event: tk.Event | None = None) -> str:
        self.run_command(self.entry.get())
        return "break"

    def on_history_up(self, _event: tk.Event | None = None) -> str:
        if not self.history:
            return "break"
        if self.history_index is None:
            self.history_index = len(self.history) - 1
        else:
            self.history_index = max(0, self.history_index - 1)
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.history_index])
        return "break"

    def on_history_down(self, _event: tk.Event | None = None) -> str:
        if not self.history:
            return "break"
        if self.history_index is None:
            return "break"
        self.history_index += 1
        if self.history_index >= len(self.history):
            self.history_index = None
            self.entry.delete(0, "end")
            return "break"
        self.entry.delete(0, "end")
        self.entry.insert(0, self.history[self.history_index])
        return "break"

    def _load_history(self) -> None:
        try:
            self.history = [line.rstrip("\n") for line in HISTORY_FILE.read_text().splitlines() if line.strip()]
        except FileNotFoundError:
            self.history = []

    def _save_history(self) -> None:
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        HISTORY_FILE.write_text("\n".join(self.history[-500:]) + ("\n" if self.history else ""))

    def run_command(self, raw: str) -> None:
        command = raw.strip()
        self.entry.delete(0, "end")
        self.history_index = None

        if not command:
            return
        if self.command_running:
            self.append_output("Another command is still running.\n", tag="error")
            return

        self.history.append(command)
        self._save_history()
        self.append_output(f"{self.prompt_var.get()} {command}\n", tag="accent")

        if command == "clear":
            self.clear_output()
            return
        if command == "pwd":
            self.append_output(f"{self.cwd}\n")
            return
        if command in {"exit", "quit"}:
            self.root.destroy()
            return
        if command == "help":
            self.append_output(
                "Built-ins:\n"
                "  help   show this help\n"
                "  cd     change directory\n"
                "  pwd    print current directory\n"
                "  clear  clear terminal output\n"
                "  exit   close the app\n\n"
                "Everything else runs through /bin/bash -lc.\n"
            )
            return
        if command.startswith("cd"):
            self.handle_cd(command)
            return

        self.command_running = True
        thread = threading.Thread(target=self._run_subprocess, args=(command,), daemon=True)
        thread.start()

    def handle_cd(self, command: str) -> None:
        parts = shlex.split(command)
        target = Path.home() if len(parts) == 1 else Path(parts[1]).expanduser()
        if not target.is_absolute():
            target = (self.cwd / target).resolve()
        if not target.exists() or not target.is_dir():
            self.append_output(f"cd: no such directory: {target}\n", tag="error")
            return
        self.cwd = target
        self.refresh_prompt()

    def _run_subprocess(self, command: str) -> None:
        try:
            proc = subprocess.run(
                ["/bin/bash", "-lc", command],
                cwd=str(self.cwd),
                text=True,
                capture_output=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            if not output:
                output = "\n"
            tag = "normal" if proc.returncode == 0 else "error"
            self.output_queue.put((output, tag))
            if proc.returncode != 0:
                self.output_queue.put((f"[exit {proc.returncode}]\n", "error"))
        except Exception as exc:  # noqa: BLE001
            self.output_queue.put((f"{type(exc).__name__}: {exc}\n", "error"))
        finally:
            self.output_queue.put(("__COMMAND_DONE__", "normal"))

    def _drain_queue(self) -> None:
        while True:
            try:
                text, tag = self.output_queue.get_nowait()
            except queue.Empty:
                break
            if text == "__COMMAND_DONE__":
                self.command_running = False
                continue
            self.append_output(text, tag=tag)
        self.root.after(100, self._drain_queue)


def main() -> None:
    root = tk.Tk()
    TerminalApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
