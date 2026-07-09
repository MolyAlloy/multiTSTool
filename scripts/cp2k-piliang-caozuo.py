#!/usr/bin/env python3
"""Batch run a command in leaf directories with optional wildcard resolution."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".cp2k_tmp",
    "__pycache__",
    ".pycache_tmp",
    "tmp",
    "temp",
    "node_modules",
}


def ask_required(question: str) -> str:
    while True:
        answer = input(question).strip()
        if answer:
            return answer
        print("This value cannot be empty.")


def ask_yes_no(question: str) -> bool:
    while True:
        answer = input(f"{question} [yes/no]: ").strip().lower()
        if answer in {"yes", "y"}:
            return True
        if answer in {"no", "n"}:
            return False
        print("Please enter yes or no.")


def ask_match_scope() -> str:
    return "all" if ask_yes_no("Execute all matching directories?") else "latest"


def ask_command() -> str:
    print("\nCommand examples:")
    print("  Multiwfn *.restart < ~/daochu.txt")
    print(r"  cp2k-zuobiaotihuan.py *.cif *.inp")
    print(r"  python D:\Data\PythonCode\multiTSplugin\cp2k-zuobiaotihuan.py *.cif *.inp")
    return ask_required("Command to run in each matched folder: ")


def find_target_dirs(search_root: Path, target: str) -> list[Path]:
    target_path = Path(target).expanduser()
    if target_path.exists():
        return [target_path.resolve()]

    matches: list[Path] = []
    target_lower = target.lower()
    for root, dirs, _files in os.walk(search_root):
        dirs[:] = [dirname for dirname in dirs if not is_ignored_dir_name(dirname)]
        root_path = Path(root)
        for dirname in dirs:
            if dirname.lower() == target_lower:
                matches.append((root_path / dirname).resolve())
    return sorted(matches)


def is_ignored_dir_name(name: str) -> bool:
    return name.startswith(".") or name.lower() in IGNORED_DIR_NAMES


def visible_child_dirs(directory: Path) -> list[Path]:
    return sorted(
        (child for child in directory.iterdir() if child.is_dir() and not is_ignored_dir_name(child.name)),
        key=path_sort_key,
    )


def collect_leaf_dirs(target_dirs: list[Path]) -> list[Path]:
    leaf_dirs: set[Path] = set()
    for target_dir in target_dirs:
        for root, dirs, _files in os.walk(target_dir):
            dirs[:] = [dirname for dirname in dirs if not is_ignored_dir_name(dirname)]
            if not dirs:
                leaf_dirs.add(Path(root).resolve())
    return sorted(leaf_dirs, key=lambda path: str(path).lower())


def collect_matching_dirs(target_dirs: list[Path], wildcard_patterns: list[str]) -> list[Path]:
    matching_dirs: set[Path] = set()
    for target_dir in target_dirs:
        for root, dirs, _files in os.walk(target_dir):
            dirs[:] = [dirname for dirname in dirs if not is_ignored_dir_name(dirname)]
            root_path = Path(root).resolve()
            if all(latest_file(root_path, pattern) is not None for pattern in wildcard_patterns):
                matching_dirs.add(root_path)
    return sorted(matching_dirs, key=lambda path: str(path).lower())


def has_wildcard(text: str) -> bool:
    return any(char in text for char in "*?[")


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = [path for path in directory.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: (path.stat().st_mtime, path.name))


def split_command(command: str) -> list[str]:
    return shlex.split(command.strip(), posix=False)


def strip_quotes(text: str) -> str:
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def command_wildcard_patterns(command: str) -> list[str]:
    patterns: list[str] = []
    for raw_token in split_command(command):
        token = strip_quotes(raw_token)
        if token == "<":
            continue
        if token.startswith("<"):
            token = token[1:]
        if has_wildcard(token):
            patterns.append(token)
    return patterns


@dataclass
class SelectedFile:
    pattern: str
    path: Path


@dataclass
class CommandPlan:
    cwd: Path
    args: list[str]
    stdin_file: Path | None
    display_command: str
    selected_files: list[SelectedFile]
    skipped_reason: str | None = None


def resolve_input_path(token: str, cwd: Path) -> Path:
    path = Path(token).expanduser()
    if not path.is_absolute():
        path = cwd / path
    return path.resolve()


def resolve_python_script(args: list[str]) -> list[str]:
    if not args:
        return args

    first = strip_quotes(args[0])
    script_index = 0
    if first.lower() in {"python", "python.exe", "py", "py.exe"} and len(args) > 1:
        script_index = 1

    script = strip_quotes(args[script_index])
    if not script.lower().endswith(".py"):
        return args

    candidates = [Path(script)]
    if not Path(script).is_absolute():
        candidates.extend([Path.cwd() / script, Path(__file__).resolve().parent / script])

    for candidate in candidates:
        if candidate.is_file():
            if script_index == 0:
                return [sys.executable, str(candidate.resolve()), *args[1:]]
            return [args[0], str(candidate.resolve()), *args[2:]]

    return args


def command_to_display(args: list[str], stdin_file: Path | None) -> str:
    text = subprocess.list2cmdline(args)
    if stdin_file is not None:
        text += f" < {stdin_file}"
    return text


def select_wildcard_file(cwd: Path, pattern: str) -> tuple[Path | None, str | None]:
    selected = latest_file(cwd, pattern)
    if selected is None:
        return None, f"no file matches {pattern}"
    return selected, None


def build_command_plan(command: str, cwd: Path, use_wildcards: bool) -> CommandPlan:
    raw_tokens = split_command(command)
    args: list[str] = []
    stdin_file: Path | None = None
    selected_files: list[SelectedFile] = []
    index = 0

    while index < len(raw_tokens):
        token = strip_quotes(raw_tokens[index])
        if token == "<":
            index += 1
            if index >= len(raw_tokens):
                return CommandPlan(cwd, [], None, command, selected_files, "redirection '<' has no input file")
            stdin_token = strip_quotes(raw_tokens[index])
            if use_wildcards and has_wildcard(stdin_token):
                selected, error = select_wildcard_file(cwd, stdin_token)
                if error:
                    return CommandPlan(cwd, [], None, command, selected_files, error)
                selected_files.append(SelectedFile(stdin_token, selected))
                stdin_file = selected.resolve()
            else:
                stdin_file = resolve_input_path(stdin_token, cwd)
            index += 1
            continue

        if token.startswith("<"):
            stdin_token = token[1:]
            if use_wildcards and has_wildcard(stdin_token):
                selected, error = select_wildcard_file(cwd, stdin_token)
                if error:
                    return CommandPlan(cwd, [], None, command, selected_files, error)
                selected_files.append(SelectedFile(stdin_token, selected))
                stdin_file = selected.resolve()
            else:
                stdin_file = resolve_input_path(stdin_token, cwd)
            index += 1
            continue

        if use_wildcards and has_wildcard(token):
            selected, error = select_wildcard_file(cwd, token)
            if error:
                return CommandPlan(cwd, [], stdin_file, command, selected_files, error)
            selected_files.append(SelectedFile(token, selected))
            args.append(selected.name)
        else:
            args.append(token)
        index += 1

    if stdin_file is not None and not stdin_file.is_file():
        return CommandPlan(cwd, [], stdin_file, command, selected_files, f"stdin file does not exist: {stdin_file}")

    args = resolve_python_script(args)
    return CommandPlan(cwd, args, stdin_file, command_to_display(args, stdin_file), selected_files)


def build_command_plans(command: str, work_dirs: list[Path], use_wildcards: bool) -> list[CommandPlan]:
    return [build_command_plan(command, work_dir, use_wildcards) for work_dir in work_dirs]


def plan_latest_mtime(plan: CommandPlan) -> float:
    mtimes = [selected.path.stat().st_mtime for selected in plan.selected_files if selected.path.is_file()]
    return max(mtimes, default=plan.cwd.stat().st_mtime)


def filter_latest_plan(plans: list[CommandPlan]) -> list[CommandPlan]:
    runnable_plans = [plan for plan in plans if plan.skipped_reason is None]
    if not runnable_plans:
        return plans[:1]
    return [max(runnable_plans, key=lambda plan: (plan_latest_mtime(plan), str(plan.cwd).lower()))]


def path_sort_key(path: Path) -> str:
    return str(path).lower()


def build_tree_lines(root: Path, plans_by_cwd: dict[Path, CommandPlan]) -> list[str]:
    lines = [str(root)]

    def append_plan_details(plan: CommandPlan, prefix: str) -> None:
        if plan.skipped_reason:
            lines.append(f"{prefix}[SKIP] {plan.skipped_reason}")
            return
        if plan.selected_files:
            for selected in plan.selected_files:
                lines.append(f"{prefix}{selected.pattern} -> {selected.path.name}")
        else:
            lines.append(f"{prefix}(command runs here)")

    def add_dir(directory: Path, prefix: str) -> None:
        try:
            children = visible_child_dirs(directory)
        except OSError as exc:
            lines.append(f"{prefix}`-- [WARN] cannot read directory: {exc}")
            return

        for index, child in enumerate(children):
            is_last = index == len(children) - 1
            branch = "`-- " if is_last else "|-- "
            child_prefix = "    " if is_last else "|   "
            child_resolved = child.resolve()
            lines.append(f"{prefix}{branch}{child.name}/")
            plan = plans_by_cwd.get(child_resolved)
            if plan is not None:
                append_plan_details(plan, prefix + child_prefix + "    ")
            add_dir(child, prefix + child_prefix)

    root_plan = plans_by_cwd.get(root.resolve())
    if root_plan is not None:
        append_plan_details(root_plan, "    ")
    add_dir(root, "")
    return lines


def print_tree(target_dirs: list[Path], plans: list[CommandPlan]) -> None:
    print("\nFound directory tree:")
    plans_by_cwd = {plan.cwd.resolve(): plan for plan in plans}
    for target_dir in target_dirs:
        for line in build_tree_lines(target_dir, plans_by_cwd):
            print(line)


def print_command_plans(plans: list[CommandPlan]) -> None:
    print("\nCommands to execute:")
    if not plans:
        print("  (no commands)")
        return
    for plan in plans:
        if plan.skipped_reason:
            print(f"[SKIP] ({plan.cwd}) {plan.skipped_reason}")
        else:
            print(f"[RUN]  ({plan.cwd}) {plan.display_command}")


def run_command_plan(plan: CommandPlan) -> bool:
    if plan.skipped_reason:
        print(f"[SKIP] ({plan.cwd}) {plan.skipped_reason}")
        return False

    print(f"[RUN] ({plan.cwd}) {plan.display_command}")
    try:
        if plan.stdin_file is None:
            result = subprocess.run(plan.args, cwd=plan.cwd, text=True, check=False)
        else:
            with plan.stdin_file.open("r", encoding="utf-8", errors="replace") as stdin:
                result = subprocess.run(plan.args, cwd=plan.cwd, stdin=stdin, text=True, check=False)
    except OSError as exc:
        print(f"[FAIL] Cannot run command in {plan.cwd}: {exc}", file=sys.stderr)
        return False

    if result.returncode != 0:
        print(f"[FAIL] Command exited with code {result.returncode}: {plan.cwd}", file=sys.stderr)
        return False

    print(f"[OK] {plan.cwd}")
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Batch run a command under a target folder. When wildcard mode is enabled, "
            "only directories matching all wildcard arguments are used; otherwise leaf directories are used."
        )
    )
    parser.add_argument(
        "target",
        nargs="?",
        help="Target directory path or directory name to search for. If omitted, ask interactively.",
    )
    parser.add_argument(
        "-s",
        "--search-root",
        default=".",
        help="Root directory used when target is a directory name. Default: current directory.",
    )
    parser.add_argument(
        "-c",
        "--command",
        help="Command template to run in each matched folder. If omitted, ask interactively.",
    )
    parser.add_argument(
        "--wildcards",
        action="store_true",
        help="Enable wildcard resolution without asking.",
    )
    parser.add_argument(
        "--no-wildcards",
        action="store_true",
        help="Disable wildcard resolution without asking.",
    )
    parser.add_argument(
        "--all-matches",
        action="store_true",
        help="Execute every directory that matches all wildcard arguments.",
    )
    parser.add_argument(
        "--latest-match",
        action="store_true",
        help="Execute only the matching directory with the newest selected wildcard file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the directory tree and commands; do not execute commands.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    search_root = Path(args.search_root).expanduser().resolve()

    if not search_root.is_dir():
        print(f"Error: search root is not a directory: {search_root}", file=sys.stderr)
        return 2
    if args.wildcards and args.no_wildcards:
        print("Error: --wildcards and --no-wildcards cannot be used together.", file=sys.stderr)
        return 2
    if args.all_matches and args.latest_match:
        print("Error: --all-matches and --latest-match cannot be used together.", file=sys.stderr)
        return 2

    target = args.target or ask_required("Target folder path or name: ")
    target_dirs = find_target_dirs(search_root, target)
    if not target_dirs:
        print(f"Error: cannot find target directory {target!r} under {search_root}", file=sys.stderr)
        return 1

    if args.wildcards:
        use_wildcards = True
    elif args.no_wildcards:
        use_wildcards = False
    else:
        use_wildcards = ask_yes_no("Enable wildcard expansion for matching files?")

    command = args.command or ask_command()
    wildcard_patterns = command_wildcard_patterns(command)
    if use_wildcards and not wildcard_patterns:
        print("[WARN] Wildcard expansion is enabled, but the command contains no wildcard arguments.")

    if use_wildcards and wildcard_patterns:
        work_dirs = collect_matching_dirs(target_dirs, wildcard_patterns)
    else:
        work_dirs = collect_leaf_dirs(target_dirs)
    plans = build_command_plans(command, work_dirs, use_wildcards)

    if use_wildcards and wildcard_patterns:
        if args.latest_match:
            match_scope = "latest"
        elif args.all_matches:
            match_scope = "all"
        else:
            match_scope = ask_match_scope()
        if match_scope == "latest":
            plans = filter_latest_plan(plans)
            if plans:
                print(f"\nSelected latest matching directory: {plans[0].cwd}")

    print_tree(target_dirs, plans)
    print_command_plans(plans)

    if args.dry_run:
        print("\nDry run only. No commands were executed.")
        return 0
    if not ask_yes_no("\nDo you want to execute these commands?"):
        print("Canceled. No commands were executed.")
        return 0

    total_success = 0
    total_failed = 0
    print("\nExecuting commands:")
    for plan in plans:
        if run_command_plan(plan):
            total_success += 1
        else:
            total_failed += 1

    print(f"\nSummary: {total_success} succeeded, {total_failed} failed/skipped.")
    return 0 if total_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
