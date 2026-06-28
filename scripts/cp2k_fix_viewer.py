"""ASE GUI helper for generating CP2K FIXED_ATOMS blocks."""
import os
import sys
import tempfile

import numpy as np


COMPONENTS_TO_FIX = "XYZ"
LIST_ITEMS_PER_LINE = 12


def read_atoms(filepath):
    """Read a structure, falling back for CIF files with identity-only symmetry."""
    from ase.io import read
    from ase.spacegroup.spacegroup import SpacegroupValueError

    try:
        return read(filepath)
    except SpacegroupValueError as original_error:
        if not filepath.lower().endswith(".cif"):
            raise
        return read_cif_as_p1(filepath, original_error)


def read_cif_as_p1(filepath, original_error):
    """Read CIF after temporarily declaring P1 for files missing SG metadata."""
    from ase.io import read

    with open(filepath, "r", encoding="utf-8", errors="replace") as handle:
        cif_text = handle.read()

    lower_text = cif_text.lower()
    has_spacegroup = (
        "_symmetry_space_group_name_h-m" in lower_text
        or "_space_group_name_h-m_alt" in lower_text
        or "_symmetry_int_tables_number" in lower_text
        or "_space_group_it_number" in lower_text
    )
    if has_spacegroup:
        raise original_error

    p1_header = (
        "_symmetry_space_group_name_H-M 'P 1'\n"
        "_symmetry_Int_Tables_number 1\n"
    )
    lines = cif_text.splitlines(keepends=True)
    insert_at = 0
    for line_index, line in enumerate(lines):
        if line.lower().startswith("data_"):
            insert_at = line_index + 1
            break
    fixed_text = "".join(lines[:insert_at]) + p1_header + "".join(lines[insert_at:])

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            suffix=".cif",
            delete=False,
            encoding="utf-8",
            newline="",
        ) as temp_file:
            temp_file.write(fixed_text)
            temp_path = temp_file.name
        return read(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


def format_cp2k_constraint(fixed_indices):
    """Return a CP2K CONSTRAINT block for 1-based atom indices."""
    indices = sorted(fixed_indices)
    lines = [
        "  &CONSTRAINT",
        "    &FIXED_ATOMS #Set atoms to be fixed",
        f"      COMPONENTS_TO_FIX {COMPONENTS_TO_FIX} #Which fractional components will be fixed, can be X, Y, Z, XY, XZ, YZ, XYZ",
    ]

    if indices:
        chunks = [
            indices[i:i + LIST_ITEMS_PER_LINE]
            for i in range(0, len(indices), LIST_ITEMS_PER_LINE)
        ]
        for chunk_index, chunk in enumerate(chunks):
            prefix = "      LIST" if chunk_index == 0 else "          "
            values = "".join(f"{idx:6d}" for idx in chunk)
            suffix = " \\" if chunk_index < len(chunks) - 1 else ""
            lines.append(f"{prefix}{values}{suffix}")
    else:
        lines.append("      LIST")

    lines.extend([
        "    &END FIXED_ATOMS",
        "  &END CONSTRAINT",
    ])
    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python cp2k_fix_viewer.py <filepath> [interval_ms]")
        sys.exit(1)

    filepath = sys.argv[1]
    interval_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 200

    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        sys.exit(1)

    from ase.gui.gui import GUI
    from ase.gui.images import Images
    from ase.gui.i18n import _
    import ase.gui.ui as ui
    import tkinter as tk
    from tkinter import scrolledtext

    atoms = read_atoms(filepath)
    images = Images([atoms])
    gui = GUI(images)

    fixed_indices = set()
    fix_window = None
    selected_label = None
    fixed_label = None
    template_text = None
    last_selection = []

    def atom_count():
        return len(gui.atoms)

    def selected_zero_based():
        mask = gui.images.selected[:atom_count()]
        return np.where(mask)[0].tolist()

    def selected_one_based():
        indices = []
        for index in selected_zero_based():
            atom = gui.atoms[index]
            indices.append(atom.index + 1)
        return indices

    def redraw_gui():
        gui.set_frame()
        gui.draw()

    def set_selection(indices):
        gui.images.selected[:atom_count()] = False
        gui.images.selected[indices] = True
        redraw_gui()
        update_panel(force=True)

    def update_template():
        template_text.config(state=tk.NORMAL)
        template_text.delete("1.0", tk.END)
        template_text.insert(tk.END, format_cp2k_constraint(fixed_indices))
        template_text.config(state=tk.DISABLED)

    def update_panel(force=False):
        nonlocal last_selection
        if fix_window is None or not fix_window.exists:
            return

        current_selection = selected_one_based()
        if not force and current_selection == last_selection:
            return

        selected_label.config(text=str(current_selection) if current_selection else "-")
        fixed_label.config(
            text=f"{len(fixed_indices)} / {atom_count()} atoms fixed"
        )
        update_template()
        last_selection = current_selection

    def on_select_all():
        set_selection(list(range(atom_count())))

    def on_reverse_select():
        mask = gui.images.selected[:atom_count()].copy()
        gui.images.selected[:atom_count()] = np.logical_not(mask)
        redraw_gui()
        update_panel(force=True)

    def on_fix():
        fixed_indices.update(selected_one_based())
        update_panel(force=True)

    def on_unfix():
        fixed_indices.difference_update(selected_one_based())
        update_panel(force=True)

    fix_window = ui.Window(_("CP2K Fixed Atoms"))
    frame = fix_window.win

    btn_frame = tk.Frame(frame)
    btn_frame.pack(fill=tk.X, padx=6, pady=6)

    tk.Button(btn_frame, text=_("select all"), command=on_select_all).pack(
        side=tk.LEFT, padx=2
    )
    tk.Button(btn_frame, text=_("reverse select"), command=on_reverse_select).pack(
        side=tk.LEFT, padx=2
    )
    tk.Button(btn_frame, text=_("fix"), command=on_fix).pack(
        side=tk.LEFT, padx=2
    )
    tk.Button(btn_frame, text=_("un-fix"), command=on_unfix).pack(
        side=tk.LEFT, padx=2
    )

    info_frame = tk.Frame(frame)
    info_frame.pack(fill=tk.X, padx=6, pady=(0, 4))

    tk.Label(info_frame, text=_("Selected atoms:")).pack(anchor=tk.W)
    selected_label = tk.Label(info_frame, text="-", anchor=tk.W, bg="white", width=64)
    selected_label.pack(fill=tk.X)

    fixed_label = tk.Label(info_frame, text="", anchor=tk.W)
    fixed_label.pack(fill=tk.X, pady=(4, 0))

    template_text = scrolledtext.ScrolledText(
        frame,
        width=86,
        height=18,
        font=("Consolas", 10),
        wrap=tk.NONE,
    )
    template_text.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

    def poll_selection(gui):
        update_panel()

    update_panel(force=True)
    gui.repeat_poll(poll_selection, interval_ms)
    gui.run()


if __name__ == "__main__":
    main()
