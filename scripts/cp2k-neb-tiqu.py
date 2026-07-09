#!/usr/bin/env python3
"""Extract the final frame from CP2K NEB replica trajectory files."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REPLICA_RE = re.compile(r"-pos-Replica_nr_(\d+)-1\.xyz$")
FLOAT_RE = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Extract the last XYZ frame from CP2K NEB replica trajectories into "
            "a neb-finished directory."
        )
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="CP2K input file, such as cp2k-neb.inp. Defaults to the only *.inp in cwd.",
    )
    parser.add_argument(
        "-p",
        "--prefix",
        help=(
            "Trajectory prefix before -pos-Replica_nr_N-1.xyz. "
            "Defaults to the input file stem."
        ),
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("neb-finished"),
        help="Output directory. Default: neb-finished",
    )
    parser.add_argument(
        "-e",
        "--energy-file",
        type=Path,
        help=(
            "CP2K NEB energy file ending with ener. The script reads the last "
            "data row and treats the negative values after the step column as energies."
        ),
    )
    return parser.parse_args()


def infer_prefix(input_file: Path | None, prefix: str | None) -> str:
    if prefix:
        return prefix

    if input_file:
        return input_file.stem

    inp_files = sorted(Path.cwd().glob("*.inp"))
    if len(inp_files) == 1:
        return inp_files[0].stem

    if not inp_files:
        raise SystemExit(
            "No *.inp file found. Use --prefix, for example: "
            "python extract_cp2k_neb_finished.py --prefix cp2k-neb"
        )

    names = ", ".join(path.name for path in inp_files)
    raise SystemExit(
        f"Found multiple *.inp files ({names}). Use --input or --prefix to choose one."
    )


def find_input_file(input_file: Path | None, prefix: str) -> Path | None:
    if input_file:
        if not input_file.is_file():
            raise SystemExit(f"Input file not found: {input_file}")
        return input_file

    prefixed = Path(f"{prefix}.inp")
    if prefixed.is_file():
        return prefixed

    inp_files = sorted(Path.cwd().glob("*.inp"))
    if len(inp_files) == 1:
        return inp_files[0]

    return None


def replica_number(path: Path) -> int:
    match = REPLICA_RE.search(path.name)
    if not match:
        raise ValueError(f"Cannot read replica number from {path.name}")
    return int(match.group(1))


def find_replica_files(prefix: str) -> list[Path]:
    name_re = re.compile(rf"^{re.escape(prefix)}-pos-Replica_nr_(\d+)-1\.xyz$")
    files = sorted(
        (path for path in Path.cwd().iterdir() if path.is_file() and name_re.match(path.name)),
        key=replica_number,
    )
    if not files:
        raise SystemExit(f"No replica trajectory files found for prefix '{prefix}'.")

    numbers = [replica_number(path) for path in files]
    expected = list(range(1, numbers[-1] + 1))
    if numbers != expected:
        raise SystemExit(
            "Replica files are not continuous from 1 to the last image. "
            f"Found: {numbers}"
        )

    return files


def read_last_xyz_frame(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    frame_start = None
    index = 0

    while index < len(lines):
        stripped = lines[index].strip()
        try:
            atom_count = int(stripped)
        except ValueError as exc:
            raise SystemExit(
                f"{path.name}: expected atom count at line {index + 1}, got {stripped!r}."
            ) from exc

        frame_end = index + atom_count + 2
        if frame_end > len(lines):
            raise SystemExit(
                f"{path.name}: incomplete XYZ frame starting at line {index + 1}."
            )

        frame_start = index
        index = frame_end

        while index < len(lines) and not lines[index].strip():
            index += 1

    if frame_start is None:
        raise SystemExit(f"{path.name}: no XYZ frame found.")

    return "\n".join(lines[frame_start:]) + "\n"


def strip_cp2k_comment(line: str) -> str:
    return line.split("#", 1)[0].split("!", 1)[0].strip()


def read_cell_vectors(path: Path | None) -> tuple[tuple[float, float, float], ...] | None:
    if path is None:
        return None

    vectors = {}
    in_cell = False

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = strip_cp2k_comment(raw_line)
        if not line:
            continue

        upper = line.upper()
        if upper.startswith("&CELL"):
            in_cell = True
            continue

        if in_cell and upper.startswith("&END"):
            break

        if not in_cell:
            continue

        parts = line.split()
        if len(parts) >= 4 and parts[0].upper() in {"A", "B", "C"}:
            try:
                vectors[parts[0].upper()] = tuple(float(value) for value in parts[1:4])
            except ValueError as exc:
                raise SystemExit(f"{path.name}: cannot parse CELL vector line: {raw_line}") from exc

    if not vectors:
        return None

    missing = [name for name in ("A", "B", "C") if name not in vectors]
    if missing:
        raise SystemExit(
            f"{path.name}: CELL section is missing vector(s): {', '.join(missing)}"
        )

    return vectors["A"], vectors["B"], vectors["C"]


def cell_comment(cell_vectors: tuple[tuple[float, float, float], ...] | None) -> str:
    if cell_vectors is None:
        return ""

    labels = ("Tv_1", "Tv_2", "Tv_3")
    parts = []
    for label, vector in zip(labels, cell_vectors):
        parts.append(
            f"{label}: {vector[0]:11.6f} {vector[1]:11.6f} {vector[2]:11.6f}"
        )
    return " ".join(parts)


def add_cell_to_xyz_frame(frame: str, cell_text: str) -> str:
    if not cell_text:
        return frame

    lines = frame.splitlines()
    if len(lines) < 2:
        raise SystemExit("Internal error: XYZ frame has fewer than two lines.")

    if "Tv_1:" not in lines[1]:
        lines[1] = f"{lines[1].rstrip()} {cell_text}".strip()

    return "\n".join(lines) + "\n"


def output_name(index: int, total: int) -> str:
    if index == 1:
        return "neb-ini-1.xyz"
    if index == total:
        return f"neb-fin-{total}.xyz"
    return f"neb-image-{index}.xyz"


def find_energy_file(prefix: str, energy_file: Path | None) -> Path | None:
    if energy_file:
        if not energy_file.is_file():
            raise SystemExit(f"Energy file not found: {energy_file}")
        return energy_file

    candidates = sorted(
        path
        for path in Path.cwd().iterdir()
        if path.is_file() and path.name.lower().endswith("ener")
    )
    if not candidates:
        return None

    prefixed = [path for path in candidates if path.name.startswith(prefix)]
    if len(prefixed) == 1:
        return prefixed[0]
    if len(candidates) == 1:
        return candidates[0]

    names = ", ".join(path.name for path in candidates)
    raise SystemExit(
        f"Found multiple energy files ending with 'ener' ({names}). "
        "Keep only one in this directory, or rename the target file to start with the prefix."
    )


def numbers_from_line(line: str) -> list[float]:
    values = []
    for text in FLOAT_RE.findall(line.replace("D", "E").replace("d", "e")):
        values.append(float(text))
    return values


def energy_values_from_row(values: list[float], replica_count: int, path: Path, line_number: int) -> list[float]:
    if len(values) < 2:
        raise SystemExit(
            f"{path.name}: line {line_number} does not contain a step plus energy values."
        )

    energies = []
    for value in values[1:]:
        if value < 0:
            energies.append(value)
            continue
        break

    if len(energies) != replica_count:
        raise SystemExit(
            f"{path.name}: line {line_number} has {len(energies)} negative energy values "
            f"after the step column, but {replica_count} replica files were found."
        )

    return energies


def read_final_step_energies(path: Path, replica_count: int) -> list[float]:
    final_values = None

    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not re.match(r"^[+-]?(?:\d|\.)", stripped):
            continue

        values = numbers_from_line(stripped)
        final_values = energy_values_from_row(values, replica_count, path, line_number)

    if final_values is None:
        raise SystemExit(f"{path.name}: no usable energy rows found.")

    return final_values


def main() -> int:
    args = parse_args()
    prefix = infer_prefix(args.input, args.prefix)
    input_file = find_input_file(args.input, prefix)
    cell_text = cell_comment(read_cell_vectors(input_file))
    replica_files = find_replica_files(prefix)

    args.output_dir.mkdir(exist_ok=True)
    total = len(replica_files)
    extracted_frames = []

    for path in replica_files:
        index = replica_number(path)
        target = args.output_dir / output_name(index, total)
        frame = add_cell_to_xyz_frame(read_last_xyz_frame(path), cell_text)
        target.write_text(frame, encoding="utf-8")
        extracted_frames.append((index, target, frame))
        print(f"{path.name} -> {target}")

    if cell_text:
        print(f"Added cell vectors from {input_file} to XYZ comment lines.")
    else:
        print("No CELL A/B/C vectors found in an input file; XYZ comment lines unchanged.")

    trajectory = args.output_dir / "guiji.xyz"
    trajectory.write_text("".join(frame for _, _, frame in extracted_frames), encoding="utf-8")
    print(f"Merged final structures -> {trajectory}")

    energy_file = find_energy_file(prefix, args.energy_file)
    if energy_file:
        energies = read_final_step_energies(energy_file, total)
        max_index = max(range(1, total + 1), key=lambda idx: energies[idx - 1])
        source = args.output_dir / output_name(max_index, total)
        marker = args.output_dir / f"neb-image-{max_index}-max.xyz"
        marker.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        print(
            f"Highest final-step energy: replica {max_index}, "
            f"E = {energies[max_index - 1]:.12g} -> {marker}"
        )
    else:
        print("No energy file ending with 'ener' found; skipped max-energy marker.")

    print(f"Done. Extracted {total} final structures into {args.output_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
