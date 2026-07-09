#!/usr/bin/env python
"""
Monitor CP2K dimer optimization energy.

Usage:
    dimer-monitor.py xxx-dimer.out

The script writes fe.dat and energy_eV.txt in the current directory, then opens a
gnuplot window that refreshes while this script keeps reparsing the CP2K output.
Stop it with Ctrl-C when you are done monitoring.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
import re
from pathlib import Path


HARTREE_TO_EV = 27.2113838
DEFAULT_GNUPLOT_X11 = Path(
    "~/.tools/gnuplot-6.0.4-install/libexec/gnuplot/6.0/gnuplot_x11"
).expanduser()

ENERGY_RE = re.compile(
    r"ENERGY\| Total FORCE_EVAL.*?([+\-]?\d+\.\d+(?:[Ee][+\-]?\d+)?)"
)
OLD_STEP_RE = re.compile(r"Informations at step")
OLD_STEP_NUM_RE = re.compile(r"at step\s+=\s+(\d+)")
OLD_MAX_GRAD_RE = re.compile(
    r"Max\. gradient\s+=\s+([+\-]?\d+\.\d+(?:[Ee][+\-]?\d+)?)"
)
NEW_STEP_RE = re.compile(r"OPT\|\s+Step number\s+(\d+)")
NEW_MAX_GRAD_RE = re.compile(
    r"OPT\|\s+Maximum gradient\s+([+\-]?\d+\.\d+(?:[Ee][+\-]?\d+)?)"
)


def parse_dimer_records(lines):
    records = []
    energy = None
    stepnum = 0
    converge = False
    i = 0

    while i < len(lines):
        line = lines[i]
        match = ENERGY_RE.search(line)
        if match:
            energy = float(match.group(1))
        elif OLD_STEP_RE.search(line):
            match = OLD_STEP_NUM_RE.search(line)
            if not match:
                i += 1
                continue
            stepnum = int(match.group(1))
            maxforce = None
            while i + 1 < len(lines):
                i += 1
                match = OLD_MAX_GRAD_RE.search(lines[i])
                if match:
                    maxforce = float(match.group(1))
                if re.search(r"---------------------------------------------------", lines[i]):
                    break
            if energy is not None:
                records.append((stepnum, energy, maxforce))
        elif NEW_STEP_RE.search(line):
            # Translational summaries use "OPT| Step number"; rotational
            # summaries use "Rotational step number" and are intentionally skipped.
            stepnum = int(NEW_STEP_RE.search(line).group(1))
            maxforce = None
            j = i + 1
            while j < len(lines) and not re.search(r"OPT\| \*{10,}", lines[j]):
                match = NEW_MAX_GRAD_RE.search(lines[j])
                if match:
                    maxforce = float(match.group(1))
                j += 1
            if energy is not None:
                records.append((stepnum, energy, maxforce))
            i = j
        elif re.search(r"GEOMETRY OPTIMIZATION COMPLETED", line):
            stepnum += 1
            converge = True
            while i < len(lines):
                match = ENERGY_RE.search(lines[i])
                if match:
                    energy = float(match.group(1))
                i += 1
        i += 1

    if converge and energy is not None:
        records.append((stepnum, energy, None))

    return records


def read_records(output_file):
    with output_file.open("r", errors="replace") as handle:
        return parse_dimer_records(handle.readlines())


def write_fe_dat(records, path):
    with path.open("w") as handle:
        handle.write("Step\tEnergy(a.u.)\tMax.Gradient\n")
        for stepnum, energy, maxforce in records:
            if maxforce is None:
                handle.write("%d\t%12.8f\n" % (stepnum, energy))
            else:
                handle.write("%d\t%12.8f\t%E\n" % (stepnum, energy, maxforce))


def write_energy_ev(records, path):
    first_energy = records[0][1]
    with path.open("w") as handle:
        for stepnum, energy, _maxforce in records:
            energy_ev = (energy - first_energy) * HARTREE_TO_EV
            handle.write("%d %.12f\n" % (stepnum, energy_ev))


def write_outputs(records, fe_path, ev_path):
    write_fe_dat(records, fe_path)
    write_energy_ev(records, ev_path)


def choose_terminal(requested):
    if requested in ("auto", "x11"):
        return "x11"
    print(
        "Only the x11 gnuplot terminal is enabled; ignoring requested terminal: %s" % requested,
        file=sys.stderr,
    )
    return "x11"


def gnuplot_terminal_script(terminal):
    return "set terminal %s persist enhanced\n" % terminal


def start_gnuplot(ev_path, interval, terminal):
    if shutil.which("gnuplot") is None:
        print("gnuplot was not found in PATH. Data files will still be updated.", file=sys.stderr)
        return None

    if not DEFAULT_GNUPLOT_X11.exists():
        print("x11gnuplot was not found: %s" % DEFAULT_GNUPLOT_X11, file=sys.stderr)
        print("Data files will still be updated.", file=sys.stderr)
        return None

    data_path = str(ev_path).replace("\\", "/")
    terminal = choose_terminal(terminal)
    script = gnuplot_terminal_script(terminal) + """
set title 'Total Energy'
set xlabel 'Optimization Step Number'
set ylabel 'Total Energy (eV)'
set grid
set key off
while (1) {
    plot '%s' using 1:2 with linespoints lt 3 lw 2 pt 13 ps 1.5
    pause %g
}
""" % (data_path, interval)
    env = dict(os.environ)
    env["GNUPLOT_DRIVER_DIR"] = str(DEFAULT_GNUPLOT_X11.parent)
    proc = subprocess.Popen(["gnuplot"], stdin=subprocess.PIPE, text=True, env=env)
    proc.stdin.write(script)
    proc.stdin.close()
    print("gnuplot terminal: %s" % terminal, flush=True)
    print("x11gnuplot: %s" % DEFAULT_GNUPLOT_X11, flush=True)
    return proc


def monitor(args):
    output_file = Path(args.output).expanduser()
    if not output_file.exists():
        print("Output file not found: %s" % output_file, file=sys.stderr)
        return 2

    fe_path = Path(args.fe)
    ev_path = Path(args.energy_ev)
    last_count = -1

    while True:
        records = read_records(output_file)
        if records:
            write_outputs(records, fe_path, ev_path)
            if len(records) != last_count:
                print("Parsed %d dimer optimization point(s)." % len(records), flush=True)
                last_count = len(records)
        elif args.once:
            print("No dimer optimization records found in %s" % output_file, file=sys.stderr)
            return 1

        if args.once:
            return 0

        time.sleep(args.interval)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Parse and monitor CP2K dimer optimization energy."
    )
    parser.add_argument("output", help="CP2K dimer output file, for example cp2k-dimer.out")
    parser.add_argument("-i", "--interval", type=float, default=10.0, help="refresh interval in seconds")
    parser.add_argument("--fe", default="fe.dat", help="output Hartree energy table")
    parser.add_argument("--energy-ev", default="energy_eV.txt", help="output relative eV energy table")
    parser.add_argument("--once", action="store_true", help="parse once and exit")
    parser.add_argument("--no-plot", action="store_true", help="do not open gnuplot")
    parser.add_argument(
        "--terminal",
        default="auto",
        help="gnuplot terminal. Only x11 is enabled; auto maps to x11. Default: auto",
    )
    args = parser.parse_args(argv)
    output_file = Path(args.output).expanduser()
    plot_proc = None

    try:
        if not output_file.exists():
            print("Output file not found: %s" % output_file, file=sys.stderr)
            return 2

        if args.once or args.no_plot:
            return monitor(args)

        records = read_records(output_file)
        if records:
            write_outputs(records, Path(args.fe), Path(args.energy_ev))
        plot_proc = start_gnuplot(Path(args.energy_ev), args.interval, args.terminal)
        if plot_proc is not None:
            print("gnuplot started. Press Ctrl-C here to stop monitoring.", flush=True)
        return monitor(args)
    except KeyboardInterrupt:
        print("\nStopped.")
        if plot_proc is not None and plot_proc.poll() is None:
            plot_proc.terminate()
        return 0


if __name__ == "__main__":
    sys.exit(main())
