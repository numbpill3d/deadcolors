#!/usr/bin/env python3
import argparse
import os
import random
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path


DEFAULT_FILE = Path.home() / ".config" / "deadcolors" / "ascii.txt"
DEFAULT_DIR = Path.home() / ".config" / "deadcolors" / "ascii.d"
SEPARATOR_RE = re.compile(r"^\s*(?:%%%+|---+|===+)(?:\s+(.+?))?\s*$")
NAME_RE = re.compile(r"^\s*(?:#|//|;)?\s*(?:name|title)\s*:\s*(.+?)\s*$", re.I)
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")

PALETTES = {
    "blood": ["31", "91", "38;5;88", "38;5;124", "38;5;196", "37"],
    "mono": ["37", "90", "97"],
    "toxic": ["32", "92", "38;5;46", "38;5;82", "37"],
    "ice": ["36", "96", "38;5;45", "38;5;81", "37"],
    "void": ["35", "95", "38;5;55", "38;5;129", "37"],
}


@dataclass(frozen=True)
class Script:
    name: str
    art: str


def visible_len(line: str) -> int:
    return len(ANSI_RE.sub("", line))


def derive_name(raw_name: str | None, art: str, fallback: str) -> str:
    if raw_name:
        return raw_name.strip()

    for line in art.splitlines():
        match = NAME_RE.match(line)
        if match:
            return match.group(1).strip()

    return fallback


def strip_name_header(art: str) -> str:
    lines = art.expandtabs(4).splitlines()
    while lines and not lines[0].strip():
        lines.pop(0)
    if lines and NAME_RE.match(lines[0]):
        lines.pop(0)
    return "\n".join(lines).strip("\n")


def parse_pack(path: Path) -> list[Script]:
    if not path.exists():
        return []

    scripts: list[Script] = []
    current: list[str] = []
    current_name: str | None = None
    fallback_index = 1

    def flush() -> None:
        nonlocal current, current_name, fallback_index
        raw = "\n".join(current).strip("\n")
        art = strip_name_header(raw)
        if art.strip():
            name = derive_name(current_name, raw, f"{path.stem}-{fallback_index}")
            scripts.append(Script(name=name, art=art))
            fallback_index += 1
        current = []
        current_name = None

    for line in path.read_text(errors="replace").splitlines():
        separator = SEPARATOR_RE.match(line)
        if separator:
            flush()
            current_name = separator.group(1)
            continue
        current.append(line)

    flush()
    return scripts


def load_scripts(source_file: Path, source_dir: Path) -> list[Script]:
    scripts = parse_pack(source_file)

    if source_dir.exists():
        for path in sorted(source_dir.glob("*.txt")):
            art = path.read_text(errors="replace").strip("\n")
            art = strip_name_header(art)
            if art.strip():
                scripts.append(Script(path.stem, art))

    return scripts


def colorize(art: str, palette: str, enabled: bool) -> str:
    if not enabled:
        return art

    colors = PALETTES[palette]
    rendered = []
    for line in art.splitlines():
        if not line:
            rendered.append("")
            continue
        color = random.choice(colors)
        rendered.append(f"\033[{color}m{line}\033[0m")
    return "\n".join(rendered)


def print_script(script: Script, args: argparse.Namespace) -> None:
    art = script.art

    if args.center:
        width = args.width or shutil.get_terminal_size(fallback=(80, 24)).columns
        lines = []
        for line in art.splitlines():
            pad = max((width - visible_len(line)) // 2, 0)
            lines.append(" " * pad + line)
        art = "\n".join(lines)

    use_color = args.color == "always" or (
        args.color == "auto" and sys.stdout.isatty() and not args.plain
    )

    if args.title:
        print(colorize(script.name, args.palette, use_color))
    print(colorize(art, args.palette, use_color))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deadcolors",
        description="Cycle custom ASCII color scripts from ~/.config/deadcolors.",
    )
    parser.add_argument("-r", "--random", action="store_true", help="print a random script")
    parser.add_argument("-n", "--name", help="print a script by name")
    parser.add_argument("-l", "--list", action="store_true", help="list available scripts")
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE, help=f"pack file, default: {DEFAULT_FILE}")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR, help=f"script directory, default: {DEFAULT_DIR}")
    parser.add_argument("--palette", choices=sorted(PALETTES), default="blood", help="ANSI color palette")
    parser.add_argument("--color", choices=["auto", "always", "never"], default="auto", help="when to colorize")
    parser.add_argument("--plain", action="store_true", help="disable color")
    parser.add_argument("--title", action="store_true", help="print the script name above the art")
    parser.add_argument("--center", action="store_true", help="center art in the terminal")
    parser.add_argument("--width", type=int, help="width used with --center")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scripts = load_scripts(args.file.expanduser(), args.dir.expanduser())

    if not scripts:
        print(
            "deadcolors: no ASCII scripts found. Add art to "
            f"{args.file.expanduser()} or {args.dir.expanduser()}/*.txt",
            file=sys.stderr,
        )
        return 1

    by_name = {script.name.lower(): script for script in scripts}

    if args.list:
        for script in scripts:
            print(script.name)
        return 0

    if args.name:
        script = by_name.get(args.name.lower())
        if not script:
            print(f"deadcolors: unknown script: {args.name}", file=sys.stderr)
            return 2
        print_script(script, args)
        return 0

    if args.random or len(scripts) > 1:
        print_script(random.choice(scripts), args)
        return 0

    print_script(scripts[0], args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
