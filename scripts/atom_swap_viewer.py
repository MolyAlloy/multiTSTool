"""Extended ASE GUI with atom selection and swapping functionality"""
import sys
import os
import json
import tempfile
import numpy as np
from pathlib import Path


def get_command_file():
    return os.path.join(tempfile.gettempdir(), "ase_gui_commands.json")


def read_command():
    filepath = get_command_file()
    if not os.path.exists(filepath):
        return None, None
    try:
        with open(filepath, "r") as f:
            data = json.load(f)
        os.remove(filepath)
        return data.get("cmd"), data.get("indices")
    except Exception:
        return None, None


def _swap_xyz_records(filepath, i, j):
    """Swap complete atom records in an XYZ file while preserving formatting."""
    path = Path(filepath)
    with path.open("r", newline="") as handle:
        text = handle.read()
    lines = text.splitlines(keepends=True)

    if len(lines) < 2:
        print(f"Invalid XYZ file: {filepath}")
        return False

    try:
        n_atoms = int(lines[0].strip())
    except ValueError:
        print(f"Invalid XYZ atom count in file: {filepath}")
        return False

    if not (0 <= i < n_atoms and 0 <= j < n_atoms):
        print(f"Invalid atom numbers: {i + 1}, {j + 1}. File has {n_atoms} atoms.")
        return False

    data_start = 2
    data_end = data_start + n_atoms
    if len(lines) < data_end:
        print(f"Invalid XYZ file: expected {n_atoms} atom records, found {max(0, len(lines) - data_start)}.")
        return False

    lines[data_start + i], lines[data_start + j] = lines[data_start + j], lines[data_start + i]
    with path.open("w", newline="") as handle:
        handle.write("".join(lines))
    return True


def swap_atoms_in_file(filepath, i, j):
    """Swap atom records at zero-based indices i and j in the file."""
    if Path(filepath).suffix.lower() == ".xyz":
        ok = _swap_xyz_records(filepath, i, j)
        if not ok:
            return False
    else:
        from ase.io import read, write

        atoms = read(filepath)

        if not (0 <= i < len(atoms) and 0 <= j < len(atoms)):
            print(f"Invalid atom numbers: {i + 1}, {j + 1}. File has {len(atoms)} atoms.")
            return False

        order = list(range(len(atoms)))
        order[i], order[j] = order[j], order[i]
        write(filepath, atoms[order])

    print(f"Swapped atom numbers {i + 1} and {j + 1} in file {filepath}", flush=True)
    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python atom_swap_viewer.py <filepath> [interval_ms]")
        sys.exit(1)

    filepath = sys.argv[1]
    interval_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 500

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    from ase.io import read
    from ase.gui.gui import GUI
    from ase.gui.images import Images
    from ase.gui.i18n import _
    import ase.gui.ui as ui
    import tkinter as tk

    atoms = read(filepath)
    images = Images([atoms])
    gui = GUI(images)

    swap_window = None
    cur_sel_label = None
    prev_sel_label = None
    atom1_var = None
    atom2_var = None
    prev_selection = []

    def get_selected_indices():
        mask = gui.images.selected[:len(gui.atoms)]
        indices = np.where(mask)[0].tolist()
        return indices

    def update_swap_panel():
        nonlocal prev_selection
        if swap_window is None or not swap_window.exists:
            return

        cur_sel = get_selected_indices()
        cur_sel_label.config(text=str([idx + 1 for idx in cur_sel]) if cur_sel else "-")
        prev_sel_label.config(text=str([idx + 1 for idx in prev_selection]) if prev_selection else "-")

        if len(cur_sel) >= 1:
            atom1_var.set(cur_sel[0] + 1)
        if len(cur_sel) >= 2:
            atom2_var.set(cur_sel[1] + 1)

        prev_selection = cur_sel

    def on_swap():
        nonlocal prev_selection
        try:
            i = atom1_var.get() - 1
            j = atom2_var.get() - 1
            if swap_atoms_in_file(filepath, i, j):
                new_atoms = read(filepath)
                gui.images.initialize([new_atoms])
                gui.set_frame()
                gui.draw()
                prev_selection = [i, j]
                update_swap_panel()
        except Exception as e:
            print(f"Swap error: {e}")

    swap_window = ui.Window(_("Atom Swap Panel"))
    frame = swap_window.win

    tk.Label(frame, text=_("Current selection (atom no.):")).pack()
    cur_sel_label = tk.Label(frame, text="-", width=30, bg="white")
    cur_sel_label.pack()

    tk.Label(frame, text=_("Previous swap (atom no.):")).pack()
    prev_sel_label = tk.Label(frame, text="-", width=30, bg="lightgray")
    prev_sel_label.pack()

    input_frame = tk.Frame(frame)
    input_frame.pack(pady=5)

    tk.Label(input_frame, text=_("Atom 1 no.:")).pack(side=tk.LEFT, padx=2)
    atom1_var = tk.IntVar(value=1)
    tk.Entry(input_frame, textvariable=atom1_var, width=6).pack(side=tk.LEFT, padx=5)

    tk.Label(input_frame, text=_("Atom 2 no.:")).pack(side=tk.LEFT, padx=2)
    atom2_var = tk.IntVar(value=1)
    tk.Entry(input_frame, textvariable=atom2_var, width=6).pack(side=tk.LEFT, padx=5)

    btn_frame = tk.Frame(frame)
    btn_frame.pack(pady=5)

    tk.Button(btn_frame, text=_("Swap & Write"), command=on_swap).pack(side=tk.LEFT, padx=2)
    tk.Button(btn_frame, text=_("Refresh"), command=update_swap_panel).pack(side=tk.LEFT, padx=2)

    last_mtime = os.path.getmtime(filepath)

    def poll_file(gui):
        nonlocal last_mtime

        cmd, indices = read_command()
        if cmd == "get_selection":
            sel = get_selected_indices()
            print(f"SELECTION:{json.dumps(sel)}", flush=True)
            return

        if not os.path.exists(filepath):
            return
        try:
            mtime = os.path.getmtime(filepath)
            if mtime != last_mtime:
                last_mtime = mtime
                new_atoms = read(filepath)
                gui.images.initialize([new_atoms])
                gui.set_frame()
                gui.draw()
        except Exception as e:
            print(f"[Poll] Error: {e}")

    gui.repeat_poll(poll_file, interval_ms)
    gui.run()


if __name__ == "__main__":
    main()
