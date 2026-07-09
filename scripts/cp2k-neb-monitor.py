#!/usr/bin/env python3
"""
Small CP2K output monitor.

It watches files matching one or more glob patterns in a directory and shows one
selected file with tail -f style live updates.
"""

from __future__ import annotations

import argparse
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, VERTICAL, BooleanVar, Button, Checkbutton, Frame, Label, Listbox, Scrollbar, StringVar, Text, Tk
from tkinter import filedialog, messagebox


DEFAULT_PATTERNS = ("*BAND*.out", "*ener*")
INITIAL_TAIL_BYTES = 128 * 1024
MAX_BUFFER_CHARS = 1_000_000
SUMMARY_ITEM = "__neb_speed_summary__"
STEP_PATTERNS = (
    re.compile(r"\bBAND\s+STEP\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"\bSTEP\s+NUMBER\s+(\d+)\b", re.IGNORECASE),
    re.compile(r"^\s*(\d+)\s+(?:DIIS|SD|CG|BFGS|LBFGS|FIRE)\b", re.IGNORECASE),
)


@dataclass
class WatchedFile:
    path: Path
    position: int = 0
    size: int = 0
    mtime: float = 0.0
    buffer: str = ""
    unread_lines: int = 0
    last_error: str = ""
    initialized: bool = False
    display_name: str = field(default="")

    def __post_init__(self) -> None:
        self.display_name = self.path.name


class Cp2kTailApp:
    def __init__(self, root: Tk, directory: Path, patterns: tuple[str, ...], interval_ms: int) -> None:
        self.root = root
        self.directory = directory
        self.patterns = patterns
        self.interval_ms = interval_ms
        self.files: dict[Path, WatchedFile] = {}
        self.ordered_paths: list[Path] = []
        self.selected_path: Path | None = None
        self.selected_summary = False
        self.summary_enabled = False
        self.summary_snapshots: dict[Path, list[tuple[float, int]]] = {}
        self.ener_line_snapshots: dict[Path, list[tuple[float, int]]] = {}
        self.last_rendered_len = 0

        self.status_var = StringVar()
        self.dir_var = StringVar(value=str(self.directory))
        self.summary_button_var = StringVar(value="Show speed summary")
        self.autoscroll_var = BooleanVar(value=True)
        self.pause_var = BooleanVar(value=False)

        self.root.title("CP2K output monitor")
        self.root.geometry("1100x720")
        self._build_ui()
        self.scan_files()
        self.poll()

    def _build_ui(self) -> None:
        top = Frame(self.root)
        top.pack(fill="x", padx=8, pady=8)

        Label(top, text="Directory:").pack(side=LEFT)
        Label(top, textvariable=self.dir_var, anchor="w").pack(side=LEFT, fill="x", expand=True, padx=6)
        Button(top, text="Change", command=self.change_directory).pack(side=LEFT, padx=4)
        Button(top, text="Refresh", command=self.scan_files).pack(side=LEFT, padx=4)
        Button(top, textvariable=self.summary_button_var, command=self.toggle_summary).pack(side=LEFT, padx=4)
        Checkbutton(top, text="Auto scroll", variable=self.autoscroll_var).pack(side=LEFT, padx=4)
        Checkbutton(top, text="Pause", variable=self.pause_var).pack(side=LEFT, padx=4)

        main = Frame(self.root)
        main.pack(fill=BOTH, expand=True, padx=8)

        left = Frame(main, width=320)
        left.pack(side=LEFT, fill="y")

        Label(left, text=f"Files: {', '.join(self.patterns)}", anchor="w").pack(fill="x")
        list_frame = Frame(left)
        list_frame.pack(fill=BOTH, expand=True)
        self.file_list = Listbox(list_frame, activestyle="dotbox", exportselection=False, width=46)
        list_scroll = Scrollbar(list_frame, orient=VERTICAL, command=self.file_list.yview)
        self.file_list.configure(yscrollcommand=list_scroll.set)
        self.file_list.pack(side=LEFT, fill=BOTH, expand=True)
        list_scroll.pack(side=RIGHT, fill="y")
        self.file_list.bind("<<ListboxSelect>>", self.on_select)

        right = Frame(main)
        right.pack(side=RIGHT, fill=BOTH, expand=True, padx=(8, 0))

        self.header = Label(right, text="Select an output file", anchor="w")
        self.header.pack(fill="x")
        text_frame = Frame(right)
        text_frame.pack(fill=BOTH, expand=True)
        self.text = Text(text_frame, wrap="none", undo=False)
        text_scroll = Scrollbar(text_frame, orient=VERTICAL, command=self.text.yview)
        self.text.configure(yscrollcommand=text_scroll.set)
        self.text.pack(side=LEFT, fill=BOTH, expand=True)
        text_scroll.pack(side=RIGHT, fill="y")

        Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=8, pady=(4, 8))

    def change_directory(self) -> None:
        selected = filedialog.askdirectory(initialdir=str(self.directory))
        if not selected:
            return
        self.directory = Path(selected)
        self.dir_var.set(str(self.directory))
        self.files.clear()
        self.ordered_paths.clear()
        self.selected_path = None
        self.selected_summary = False
        self.summary_snapshots.clear()
        self.ener_line_snapshots.clear()
        self.last_rendered_len = 0
        self.text.delete("1.0", END)
        self.scan_files()

    def toggle_summary(self) -> None:
        self.summary_enabled = not self.summary_enabled
        self.summary_button_var.set("Hide speed summary" if self.summary_enabled else "Show speed summary")
        if self.summary_enabled:
            self.selected_summary = True
            self.selected_path = None
            self.last_rendered_len = 0
        elif self.selected_summary:
            self.selected_summary = False
            self.selected_path = self.ordered_paths[0] if self.ordered_paths else None
            self.last_rendered_len = 0
        self.refresh_file_list()
        self.render_selected(force=True)

    def matching_paths(self) -> list[Path]:
        paths: set[Path] = set()
        for pattern in self.patterns:
            paths.update(p.resolve() for p in self.directory.glob(pattern) if p.is_file())
        return sorted(paths, key=lambda p: p.name.lower())

    def scan_files(self) -> None:
        try:
            paths = self.matching_paths()
        except OSError as exc:
            messagebox.showerror("Scan failed", str(exc))
            return

        for path in paths:
            self.files.setdefault(path, WatchedFile(path))

        for path in list(self.files):
            if path not in paths:
                del self.files[path]
                if self.selected_path == path:
                    self.selected_path = None

        self.ordered_paths = paths
        if self.selected_path is None and paths and not self.selected_summary:
            self.selected_path = paths[0]
            self.last_rendered_len = 0
        self.refresh_file_list()
        self.render_selected(force=True)

    def poll(self) -> None:
        if not self.pause_var.get():
            self.scan_files()
            for path in self.ordered_paths:
                self.read_new_data(self.files[path])
            self.update_summary_snapshots()
            self.refresh_file_list()
            self.render_selected()
            self.status_var.set(
                f"Watching {len(self.ordered_paths)} file(s), last update {time.strftime('%H:%M:%S')}"
            )
        self.root.after(self.interval_ms, self.poll)

    def read_new_data(self, item: WatchedFile) -> None:
        try:
            stat = item.path.stat()
            item.size = stat.st_size
            item.mtime = stat.st_mtime

            if item.position > item.size:
                item.position = 0
                item.buffer += "\n--- file truncated or rotated ---\n"

            with item.path.open("rb") as handle:
                if not item.initialized:
                    item.position = max(0, item.size - INITIAL_TAIL_BYTES)
                    handle.seek(item.position)
                    if item.position:
                        item.buffer = "--- showing recent output only ---\n"
                else:
                    handle.seek(item.position)

                raw = handle.read()
                item.position = handle.tell()

            if raw:
                text = raw.decode("utf-8", errors="replace")
                item.buffer += text
                if item.path != self.selected_path:
                    item.unread_lines += max(1, text.count("\n"))

            if len(item.buffer) > MAX_BUFFER_CHARS:
                item.buffer = item.buffer[-MAX_BUFFER_CHARS:]
            item.initialized = True
            item.last_error = ""
        except OSError as exc:
            item.last_error = str(exc)

    def update_summary_snapshots(self) -> None:
        now = time.time()
        for path in self.ordered_paths:
            item = self.files[path]
            snapshots = self.summary_snapshots.setdefault(path, [])
            if snapshots and snapshots[-1][1] == item.size:
                continue
            snapshots.append((now, item.size))
            cutoff = now - 30 * 60
            self.summary_snapshots[path] = [(stamp, size) for stamp, size in snapshots if stamp >= cutoff]

            if self.is_energy_file(path):
                line_count = self.count_energy_lines(path)
                line_snapshots = self.ener_line_snapshots.setdefault(path, [])
                if not line_snapshots or line_snapshots[-1][1] != line_count:
                    line_snapshots.append((now, line_count))
                self.ener_line_snapshots[path] = [
                    (stamp, count) for stamp, count in line_snapshots if stamp >= cutoff
                ]

    def refresh_file_list(self) -> None:
        current_selection = self.selected_path
        self.file_list.delete(0, END)
        offset = 0
        if self.summary_enabled:
            self.file_list.insert(END, "NEB speed summary")
            offset = 1
        for path in self.ordered_paths:
            item = self.files[path]
            status = f"{item.display_name}  {item.size / 1024:.1f} KiB"
            if item.unread_lines:
                status += f"  +{item.unread_lines} lines"
            if item.last_error:
                status += "  ERROR"
            self.file_list.insert(END, status)

        if self.selected_summary and self.summary_enabled:
            self.file_list.selection_set(0)
            self.file_list.activate(0)
        elif current_selection in self.ordered_paths:
            index = self.ordered_paths.index(current_selection)
            index += offset
            self.file_list.selection_set(index)
            self.file_list.activate(index)

    def on_select(self, _event: object) -> None:
        selected = self.file_list.curselection()
        if not selected:
            return
        index = selected[0]
        if self.summary_enabled and index == 0:
            self.selected_summary = True
            self.selected_path = None
            self.last_rendered_len = 0
            self.render_selected(force=True)
            self.refresh_file_list()
            return

        if self.summary_enabled:
            index -= 1
        if index < 0 or index >= len(self.ordered_paths):
            return
        self.selected_summary = False
        self.selected_path = self.ordered_paths[index]
        self.files[self.selected_path].unread_lines = 0
        self.last_rendered_len = 0
        self.render_selected(force=True)
        self.refresh_file_list()

    def render_selected(self, force: bool = False) -> None:
        if self.selected_summary:
            summary = self.build_speed_summary()
            self.header.configure(text="NEB speed summary")
            self.text.delete("1.0", END)
            self.text.insert(END, summary)
            self.last_rendered_len = len(summary)
            if self.autoscroll_var.get():
                self.text.see(END)
            return

        if self.selected_path is None:
            self.header.configure(text="No files found")
            return

        item = self.files[self.selected_path]
        self.header.configure(text=str(item.path))
        if force:
            self.text.delete("1.0", END)
            self.text.insert(END, item.buffer)
            self.last_rendered_len = len(item.buffer)
        elif len(item.buffer) > self.last_rendered_len:
            self.text.insert(END, item.buffer[self.last_rendered_len :])
            self.last_rendered_len = len(item.buffer)

        item.unread_lines = 0
        if self.autoscroll_var.get():
            self.text.see(END)

    def build_speed_summary(self) -> str:
        now = time.time()
        band_paths = [path for path in self.ordered_paths if "BAND" in path.name.upper()]
        energy_paths = [path for path in self.ordered_paths if "BAND" not in path.name.upper()]
        lines = [
            "NEB speed summary",
            f"Directory: {self.directory}",
            f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        if not self.ordered_paths:
            lines.append("No matching CP2K output files found.")
            return "\n".join(lines)

        lines.extend(
            [
                "How to use this for OMP ratio tests:",
                "  - Run each MPI/OpenMP setting in a separate clean directory.",
                "  - Compare the same time window after the first BAND step has started.",
                "  - Prefer average step time from CP2K output when available; file growth rate is only a liveness proxy.",
                "",
                f"Files: {len(self.ordered_paths)} total, {len(band_paths)} BAND-like, {len(energy_paths)} other",
                "",
            ]
        )

        rows = []
        for path in self.ordered_paths:
            item = self.files[path]
            age = max(0.0, now - item.mtime) if item.mtime else 0.0
            rate = self.growth_rate_kib_per_min(path)
            latest_step = self.latest_step(item.buffer)
            rows.append((age, path, item, rate, latest_step))

        lines.append("Live files")
        lines.append("  File                                      Size      Age       Growth       Latest step")
        lines.append("  " + "-" * 89)
        for age, path, item, rate, latest_step in sorted(rows, key=lambda row: row[0]):
            age_text = self.format_duration(age)
            rate_text = f"{rate:7.1f} KiB/min" if rate is not None else "      n/a"
            step_text = str(latest_step) if latest_step is not None else "n/a"
            name = path.name[:40].ljust(40)
            lines.append(f"  {name} {item.size / 1024:8.1f} KiB  {age_text:>8}  {rate_text:>14}  {step_text:>11}")

        active = [row for row in rows if row[0] <= 180]
        stale = [row for row in rows if row[0] > 180]
        lines.extend(
            [
                "",
                f"Activity: {len(active)} file(s) updated within 3 min, {len(stale)} stale file(s).",
                "",
            ]
        )

        energy_timing = self.build_energy_timing_section()
        if energy_timing:
            lines.extend(energy_timing)
            lines.append("")

        step_values = [row[4] for row in rows if row[4] is not None]
        if step_values:
            lines.append(f"Detected latest optimizer step range: {min(step_values)} to {max(step_values)}")
        else:
            lines.append("No optimizer step number detected yet in the buffered output.")

        lines.extend(
            [
                "",
                "Tip:",
                "  For a clean speed comparison, record the wall time for equal BAND step intervals",
                "  in both test directories, for example steps 2-5 or 2-10.",
            ]
        )
        return "\n".join(lines)

    def build_energy_timing_section(self) -> list[str]:
        energy_paths = [path for path in self.ordered_paths if self.is_energy_file(path)]
        if not energy_paths:
            return []

        lines = [
            "ENER line timing",
            "  Each added line is treated as one completed full-band energy evaluation.",
            "  File                                      Lines   Last line time   Avg line time",
            "  " + "-" * 91,
        ]
        for path in energy_paths:
            snapshots = self.ener_line_snapshots.get(path, [])
            line_count = snapshots[-1][1] if snapshots else self.count_energy_lines(path)
            intervals = self.line_intervals(snapshots)
            if intervals:
                last_text = self.format_duration(intervals[-1])
                avg_text = self.format_duration(sum(intervals) / len(intervals))
            else:
                last_text = "n/a"
                avg_text = "n/a"
            name = path.name[:40].ljust(40)
            lines.append(f"  {name} {line_count:7d}   {last_text:>14}   {avg_text:>13}")
        return lines

    def growth_rate_kib_per_min(self, path: Path) -> float | None:
        snapshots = self.summary_snapshots.get(path, [])
        if len(snapshots) < 2:
            return None
        start_time, start_size = snapshots[0]
        end_time, end_size = snapshots[-1]
        elapsed = end_time - start_time
        if elapsed <= 0:
            return None
        return ((end_size - start_size) / 1024) / (elapsed / 60)

    @staticmethod
    def is_energy_file(path: Path) -> bool:
        name = path.name.lower()
        return "ener" in name

    @staticmethod
    def count_energy_lines(path: Path) -> int:
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                return sum(1 for line in handle if line.strip() and not line.lstrip().startswith("#"))
        except OSError:
            return 0

    @staticmethod
    def line_intervals(snapshots: list[tuple[float, int]]) -> list[float]:
        intervals: list[float] = []
        for (prev_time, prev_count), (next_time, next_count) in zip(snapshots, snapshots[1:]):
            delta_count = next_count - prev_count
            if delta_count <= 0:
                continue
            delta_time = next_time - prev_time
            intervals.extend([delta_time / delta_count] * delta_count)
        return intervals

    @staticmethod
    def latest_step(text: str) -> int | None:
        latest: int | None = None
        tail = text[-200_000:]
        for line in tail.splitlines():
            for pattern in STEP_PATTERNS:
                match = pattern.search(line)
                if match:
                    latest = int(match.group(1))
        return latest

    @staticmethod
    def format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        minutes = seconds / 60
        if minutes < 60:
            return f"{minutes:.1f}m"
        hours = minutes / 60
        return f"{hours:.1f}h"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor CP2K output files with a small GUI.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory containing CP2K output files.")
    parser.add_argument(
        "--pattern",
        action="append",
        dest="patterns",
        help="Glob pattern to watch. Can be used multiple times. Default: *BAND*.out and *ener*",
    )
    parser.add_argument("--interval", type=float, default=1.0, help="Refresh interval in seconds.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    directory = Path(args.directory).expanduser().resolve()
    if not directory.exists():
        raise SystemExit(f"Directory does not exist: {directory}")
    if not directory.is_dir():
        raise SystemExit(f"Not a directory: {directory}")

    patterns = tuple(args.patterns) if args.patterns else DEFAULT_PATTERNS
    root = Tk()
    Cp2kTailApp(root, directory, patterns, max(100, int(args.interval * 1000)))
    root.mainloop()


if __name__ == "__main__":
    main()
