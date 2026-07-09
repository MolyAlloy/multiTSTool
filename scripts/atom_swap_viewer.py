"""Extended ASE GUI with atom selection and swapping functionality"""
import sys
import os
import json
import tempfile
import numpy as np


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


def swap_atoms_in_file(filepath, i, j):
    """Swap positions of atoms at indices i and j in the file"""
    from ase.io import read, write
    import numpy as np

    atoms = read(filepath)

    if not (0 <= i < len(atoms) and 0 <= j < len(atoms)):
        print(f"Invalid indices: {i}, {j}. File has {len(atoms)} atoms.")
        return False

    pos_i = atoms[i].position.copy()
    pos_j = atoms[j].position.copy()
    atoms[i].position = pos_j
    atoms[j].position = pos_i

    atoms.write(filepath)
    print(f"Swapped position of atom {i} with atom {j} in file {filepath}", flush=True)
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
        cur_sel_label.config(text=str(cur_sel) if cur_sel else "-")
        prev_sel_label.config(text=str(prev_selection) if prev_selection else "-")

        if len(cur_sel) >= 1:
            atom1_var.set(cur_sel[0])
        if len(cur_sel) >= 2:
            atom2_var.set(cur_sel[1])

        prev_selection = cur_sel

    def on_swap():
        try:
            i = atom1_var.get()
            j = atom2_var.get()
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

    tk.Label(frame, text=_("Current selection:")).pack()
    cur_sel_label = tk.Label(frame, text="-", width=30, bg="white")
    cur_sel_label.pack()

    tk.Label(frame, text=_("Previous swap:")).pack()
    prev_sel_label = tk.Label(frame, text="-", width=30, bg="lightgray")
    prev_sel_label.pack()

    input_frame = tk.Frame(frame)
    input_frame.pack(pady=5)

    tk.Label(input_frame, text=_("Atom 1 index:")).pack(side=tk.LEFT, padx=2)
    atom1_var = tk.IntVar(value=0)
    tk.Entry(input_frame, textvariable=atom1_var, width=6).pack(side=tk.LEFT, padx=5)

    tk.Label(input_frame, text=_("Atom 2 index:")).pack(side=tk.LEFT, padx=2)
    atom2_var = tk.IntVar(value=0)
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