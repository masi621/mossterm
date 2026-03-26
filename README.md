# MOSS Terminal

A simple terminal-style desktop app for DebianMOSS.

It is not a full VT100 emulator. Instead, it gives you a clean terminal UI with:
- command history
- built-in `cd`, `pwd`, `clear`, `help`, and `exit`
- customizable color themes
- adjustable font size
- copy support
- a desktop launcher via `mossapp.json`

## Install with mosspkg

From a local checkout:

```bash
mosspkg install ./moss-terminal
```

From GitHub:

```bash
mosspkg install yourname/moss-terminal
```

## Run

```bash
moss-terminal
```

## Notes

- Requires Python 3 and Tkinter.
- On DebianMOSS, `python3-tk` should be present.
