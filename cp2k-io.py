#!/usr/bin/env python3
"""CP2K structure I/O helper for restart, CIF/XYZ, and template workflows."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


MULTIWFN_CP2K_INPUT = "cp2k\n\n0\nq\n"
DEFAULT_MULTIWFN = "Multiwfn"
DEFAULT_DAOCHU = Path.home() / "daochu.txt"
DEFAULT_CIF_NAME = "youhuawan.cif"
STRUCTURE_SUFFIXES = {".cif", ".xyz"}
TEMPLATE_ENV_VAR = "CP2K_IO_TEMPLATE_ROOT"
DEFAULT_TEMPLATE_RELATIVE = Path("templates") / "cp2k"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="gbk", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def ask_text(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"{prompt}{suffix}: ").strip()
    return answer or (default or "")


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    default_text = "yes" if default else "no"
    while True:
        answer = ask_text(prompt, default_text).lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please enter yes or no.")


def choose_from_list(title: str, items: list[Path], label_func=str) -> Path:
    if not items:
        raise SystemExit(f"No items available for: {title}")
    if len(items) == 1:
        print(f"{title}: {label_func(items[0])}")
        return items[0]

    print(f"\n{title}")
    for index, item in enumerate(items, start=1):
        print(f"{index}. {label_func(item)}")
    while True:
        answer = ask_text("Choose number")
        try:
            choice = int(answer)
        except ValueError:
            print("Please enter a number.")
            continue
        if 1 <= choice <= len(items):
            return items[choice - 1]
        print(f"Please choose 1-{len(items)}.")


def find_coord_block(text: str) -> re.Match[str]:
    pattern = re.compile(
        r"(?im)^(?P<coord_indent>[ \t]*)&COORD\b[^\r\n]*(?:\r?\n)"
        r"(?P<body>.*?)"
        r"^(?P<end_indent>[ \t]*)&END\s+COORD\b[^\r\n]*(?:\r?\n|$)",
        re.DOTALL,
    )
    match = pattern.search(text)
    if not match:
        raise ValueError("Cannot find an &COORD ... &END COORD block.")
    return match


def detect_line_ending(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def detect_coord_indent(template_body: str, coord_indent: str) -> str:
    for line in template_body.splitlines():
        stripped = line.strip()
        if stripped and not stripped.upper().startswith("&"):
            return line[: len(line) - len(line.lstrip(" \t"))]
    return coord_indent + "  "


def format_coord_block(generated_text: str, target_match: re.Match[str], newline: str) -> str:
    generated_match = find_coord_block(generated_text)
    coord_indent = target_match.group("coord_indent")
    end_indent = target_match.group("end_indent")
    atom_indent = detect_coord_indent(target_match.group("body"), coord_indent)

    atom_lines: list[str] = []
    for line in generated_match.group("body").splitlines():
        stripped = line.strip()
        atom_lines.append(atom_indent + stripped if stripped else "")

    return newline.join([coord_indent + "&COORD", *atom_lines, end_indent + "&END COORD"]) + newline


def replace_coord_block(target_text: str, generated_text: str) -> str:
    newline = detect_line_ending(target_text)
    target_match = find_coord_block(target_text)
    replacement = format_coord_block(generated_text, target_match, newline)
    return target_text[: target_match.start()] + replacement + target_text[target_match.end() :]


def executable_exists(name: str) -> bool:
    return shutil.which(name) is not None or Path(name).is_file()


def check_multiwfn(multiwfn: str) -> None:
    if not executable_exists(multiwfn):
        raise SystemExit(
            f"Cannot find Multiwfn executable: {multiwfn}\n"
            "Add Multiwfn to PATH or pass its full path with --multiwfn."
        )


def run_multiwfn_cp2k_export(structure_file: Path, multiwfn: str) -> Path:
    check_multiwfn(multiwfn)
    generated_inp = structure_file.with_suffix(".inp")
    before_mtime = generated_inp.stat().st_mtime if generated_inp.exists() else None

    try:
        result = subprocess.run(
            [multiwfn, structure_file.name],
            cwd=structure_file.parent,
            input=MULTIWFN_CP2K_INPUT,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to start Multiwfn: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"Multiwfn exited with code {result.returncode} for {structure_file.name}.")
    if not generated_inp.is_file():
        raise RuntimeError(f"Multiwfn did not create expected file: {generated_inp}")
    if before_mtime is not None and generated_inp.stat().st_mtime == before_mtime:
        print(f"Warning: {generated_inp.name} existed and its mtime did not change.", file=sys.stderr)
    return generated_inp


def latest_file(directory: Path, pattern: str) -> Path | None:
    files = [path for path in directory.glob(pattern) if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: (path.stat().st_mtime, path.name))


def current_structure_files(directory: Path) -> list[Path]:
    return sorted(
        (path for path in directory.iterdir() if path.is_file() and path.suffix.lower() in STRUCTURE_SUFFIXES),
        key=lambda path: path.name.lower(),
    )


def current_inp_files(directory: Path) -> list[Path]:
    return sorted((path for path in directory.glob("*.inp") if path.is_file()), key=lambda path: path.name.lower())


def choose_current_structure(directory: Path) -> Path:
    return choose_from_list(
        "Choose structure file from current directory",
        current_structure_files(directory),
        label_func=lambda path: path.name,
    )


def choose_current_inp(directory: Path) -> Path:
    return choose_from_list(
        "Choose target CP2K inp from current directory",
        current_inp_files(directory),
        label_func=lambda path: path.name,
    )


def replace_inp_coords_from_structure(
    structure_file: Path,
    target_inp: Path,
    multiwfn: str,
    keep_temp: bool = False,
) -> None:
    generated_inp = run_multiwfn_cp2k_export(structure_file, multiwfn)
    updated_text = replace_coord_block(read_text(target_inp), read_text(generated_inp))
    write_text(target_inp, updated_text)
    print(f"Updated coordinates in: {target_inp}")

    if not keep_temp and generated_inp.resolve() not in {structure_file.resolve(), target_inp.resolve()}:
        try:
            generated_inp.unlink()
            print(f"Deleted temporary file: {generated_inp}")
        except OSError as exc:
            print(f"Warning: failed to delete temporary file {generated_inp}: {exc}", file=sys.stderr)


def restart_to_cif(
    restart_file: Path,
    output_name: str,
    input_file: Path,
    multiwfn: str,
    overwrite: bool,
) -> None:
    check_multiwfn(multiwfn)
    if not restart_file.is_file():
        raise SystemExit(f"Restart file not found: {restart_file}")
    if not input_file.is_file():
        raise SystemExit(f"Multiwfn input file not found: {input_file}")

    output_path = restart_file.parent / output_name
    if output_path.exists() and not overwrite:
        raise SystemExit(f"Output CIF already exists: {output_path}")

    print(f"[RUN] ({restart_file.parent}) {multiwfn} {restart_file.name} < {input_file}")
    try:
        with input_file.open("r", encoding="utf-8", errors="replace") as stdin:
            result = subprocess.run(
                [multiwfn, restart_file.name],
                cwd=restart_file.parent,
                stdin=stdin,
                text=True,
                check=False,
            )
    except OSError as exc:
        raise RuntimeError(f"Failed to start Multiwfn: {exc}") from exc

    if result.returncode != 0:
        raise RuntimeError(f"Multiwfn exited with code {result.returncode} for {restart_file.name}.")
    if not output_path.exists():
        raise RuntimeError(f"Multiwfn finished, but expected CIF was not found: {output_path}")
    print(f"[OK] {output_path}")


def interactive_restart_to_cif(args: argparse.Namespace) -> None:
    cwd = Path.cwd()
    default_restart = latest_file(cwd, "*.restart")
    restart_text = ask_text("Restart file", str(default_restart) if default_restart else "")
    if not restart_text:
        raise SystemExit("No restart file selected.")

    output_name = ask_text("Output CIF name", DEFAULT_CIF_NAME)
    daochu_text = ask_text("Multiwfn input redirection file", str(DEFAULT_DAOCHU))
    overwrite = args.overwrite or ask_yes_no("Overwrite output CIF if it exists?", False)

    restart_to_cif(
        restart_file=Path(restart_text).expanduser().resolve(),
        output_name=output_name,
        input_file=Path(daochu_text).expanduser().resolve(),
        multiwfn=args.multiwfn,
        overwrite=overwrite,
    )


def interactive_replace_current(args: argparse.Namespace) -> None:
    cwd = Path.cwd()
    structure_file = choose_current_structure(cwd)
    target_inp = choose_current_inp(cwd)
    if not ask_yes_no(f"Replace &COORD in {target_inp.name}?", True):
        print("Canceled.")
        return
    replace_inp_coords_from_structure(structure_file, target_inp, args.multiwfn, args.keep_temp)


def path_candidates_from_anchor(anchor: Path) -> list[Path]:
    candidates: list[Path] = []
    resolved = anchor.resolve()
    starts = [resolved if resolved.is_dir() else resolved.parent]

    for start in starts:
        for parent in [start, *start.parents]:
            candidates.append(parent / DEFAULT_TEMPLATE_RELATIVE)
            candidates.append(parent / "multiTSTool" / DEFAULT_TEMPLATE_RELATIVE)

    return candidates


def template_root_candidates(args: argparse.Namespace) -> list[Path]:
    candidates: list[Path] = []
    if args.template_root:
        candidates.append(args.template_root.expanduser())

    env_value = os.environ.get(TEMPLATE_ENV_VAR)
    if env_value:
        candidates.append(Path(env_value).expanduser())

    candidates.extend(path_candidates_from_anchor(Path.cwd()))
    candidates.extend(path_candidates_from_anchor(Path(__file__)))

    unique: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        if resolved not in seen:
            seen.add(resolved)
            unique.append(resolved)
    return unique


def resolve_template_root(args: argparse.Namespace) -> Path:
    for candidate in template_root_candidates(args):
        if candidate.is_dir():
            return candidate

    searched = "\n".join(f"  - {path}" for path in template_root_candidates(args)[:10])
    raise SystemExit(
        "No CP2K template root was found.\n"
        f"Create {DEFAULT_TEMPLATE_RELATIVE}, pass --template-root, or set {TEMPLATE_ENV_VAR}.\n"
        f"Searched:\n{searched}"
    )


def select_template_library(args: argparse.Namespace) -> Path:
    template_root = resolve_template_root(args)
    libraries = sorted((path for path in template_root.iterdir() if path.is_dir()), key=lambda path: path.name.lower())
    if not libraries:
        raise SystemExit(f"No template libraries found under: {template_root}")

    print(f"\nTemplate root: {template_root}")
    return choose_from_list(
        "Choose template library",
        libraries,
        label_func=lambda path: path.name,
    )


def choose_template_file(root: Path) -> Path:
    current = root
    while True:
        child_dirs = sorted((path for path in current.iterdir() if path.is_dir()), key=lambda path: path.name.lower())
        inp_files = sorted((path for path in current.glob("*.inp") if path.is_file()), key=lambda path: path.name.lower())

        print(f"\nTemplate path: {current}")
        number = 1
        choices: list[tuple[str, Path]] = []
        for directory in child_dirs:
            print(f"{number}. [dir] {directory.name}")
            choices.append(("dir", directory))
            number += 1
        for inp_file in inp_files:
            print(f"{number}. [inp] {inp_file.name}")
            choices.append(("inp", inp_file))
            number += 1

        if current != root:
            print("0. Back")
        print("q. Cancel")

        answer = ask_text("Choose number")
        if answer.lower() == "q":
            raise SystemExit("Canceled.")
        if answer == "0" and current != root:
            current = current.parent
            continue
        try:
            choice = int(answer)
        except ValueError:
            print("Please enter a number.")
            continue
        if not 1 <= choice <= len(choices):
            print(f"Please choose 1-{len(choices)}.")
            continue

        kind, path = choices[choice - 1]
        if kind == "dir":
            current = path
        else:
            return path


def copy_template_to_current(template_file: Path, cwd: Path, overwrite: bool) -> Path:
    target = cwd / template_file.name
    if target.exists() and not overwrite:
        if not ask_yes_no(f"{target.name} already exists. Overwrite it?", False):
            raise SystemExit("Canceled.")
    shutil.copy2(template_file, target)
    print(f"Copied template: {template_file} -> {target}")
    return target


def interactive_template_to_current(args: argparse.Namespace) -> None:
    cwd = Path.cwd()
    structure_file = choose_current_structure(cwd)
    root = select_template_library(args)
    template_file = choose_template_file(root)
    target_inp = copy_template_to_current(template_file, cwd, args.overwrite)
    replace_inp_coords_from_structure(structure_file, target_inp, args.multiwfn, args.keep_temp)


def interactive_menu(args: argparse.Namespace) -> int:
    print("CP2K I/O helper")
    print(f"Current directory: {Path.cwd()}")
    print("")
    print("1. restart -> cif")
    print("2. replace &COORD in current-directory inp from current structure file")
    print("3. copy a template from template library, then replace its &COORD")
    print("q. quit")

    choice = ask_text("Choose operation")
    try:
        if choice == "1":
            interactive_restart_to_cif(args)
        elif choice == "2":
            interactive_replace_current(args)
        elif choice == "3":
            interactive_template_to_current(args)
        elif choice.lower() == "q":
            return 0
        else:
            print("Please choose 1, 2, 3, or q.")
            return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CP2K structure I/O helper.")
    parser.add_argument("--multiwfn", default=DEFAULT_MULTIWFN, help="Multiwfn executable name or full path.")
    parser.add_argument("--keep-temp", action="store_true", help="Keep temporary Multiwfn-generated .inp files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files without asking.")
    parser.add_argument(
        "--template-root",
        type=Path,
        help=f"CP2K template root. Default: auto-detect {DEFAULT_TEMPLATE_RELATIVE} or {TEMPLATE_ENV_VAR}.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    return interactive_menu(args)


if __name__ == "__main__":
    raise SystemExit(main())
