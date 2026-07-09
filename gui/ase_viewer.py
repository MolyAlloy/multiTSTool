"""ASE viewer integration"""
import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os
from pathlib import Path

try:
    from ase.io import read
    ASE_AVAILABLE = True
except ImportError:
    ASE_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"


class ASEViewer(ttk.Frame):
    def __init__(
        self,
        parent,
        controller,
        on_file_opened=None,
        open_command=None,
        save_command=None,
        cp2k_fix_command=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.on_file_opened = on_file_opened
        self.open_command = open_command
        self.save_command = save_command
        self.cp2k_fix_command = cp2k_fix_command
        self.current_filepath = None
        self._polling = False
        self._process = None
        self._create_widgets()

    def _create_widgets(self):
        view_frame = ttk.LabelFrame(self, text="ASE-Based Tools", padding="5")
        view_frame.pack(fill=tk.BOTH, expand=True)

        file_frame = ttk.Frame(view_frame)
        file_frame.pack(fill=tk.X, pady=(5, 3))

        ttk.Button(
            file_frame,
            text="Open Structure",
            command=self.open_command if self.open_command else self.open_ase_viewer
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            file_frame,
            text="Save Structure",
            command=self.save_command if self.save_command else self._noop
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            file_frame,
            text="CP2K-FIX",
            command=self.cp2k_fix_command if self.cp2k_fix_command else self._noop
        ).pack(side=tk.LEFT, padx=5)

        ase_frame = ttk.Frame(view_frame)
        ase_frame.pack(fill=tk.X, pady=(3, 8))

        viewer_buttons = [
            ttk.Button(
                ase_frame,
                text="Live Poll",
                command=self.open_with_poll
            ),
            ttk.Button(
                ase_frame,
                text="Atom Swap",
                command=self.open_atom_swap_viewer
            ),
        ]

        for button in viewer_buttons:
            button.pack(side=tk.LEFT, padx=5)

        if not ASE_AVAILABLE:
            for button in viewer_buttons:
                button.configure(state=tk.DISABLED)
            ttk.Label(
                view_frame,
                text="ASE not available. Install: pip install ase"
            ).pack(anchor=tk.W, padx=5, pady=(0, 4))

    def _noop(self):
        return

    def open_ase_viewer(self):
        """Open current structure in ASE viewer (no polling)"""
        filepath = self._get_filepath()
        if filepath is None:
            return
        self.current_filepath = filepath
        self._launch_subprocess(filepath, poll=False)

    def open_with_poll(self):
        """Open ASE viewer with file polling enabled"""
        filepath = self._get_filepath()
        if filepath is None:
            return
        self.current_filepath = filepath
        self._launch_subprocess(filepath, poll=True)

    def open_atom_swap_viewer(self):
        """Open ASE viewer with atom swap panel"""
        filepath = self._get_filepath()
        if filepath is None:
            return
        self.current_filepath = filepath
        script = SCRIPT_DIR / "atom_swap_viewer.py"
        filepath = str(Path(filepath).resolve())
        cmd = [sys.executable, str(script), filepath]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(Path(filepath).parent)
        )
        self._polling = False
        if self.on_file_opened:
            self.on_file_opened(filepath)

    def _get_filepath(self):
        """Get file path from controller or file dialog"""
        filepath = self.controller.get_current_filepath()
        if filepath is None:
            from tkinter import filedialog
            initialdir = None
            current_path = getattr(self.on_file_opened, "__self__", None)
            if current_path is not None and hasattr(current_path, "current_path"):
                initialdir = str(current_path.current_path)
            filepath = filedialog.askopenfilename(
                title="Select file to open",
                initialdir=initialdir,
                filetypes=[
                    ("Structure files", "*.xyz *.vasp *.cif CONTCAR POSCAR"),
                    ("All files", "*.*")
                ]
            )
            if not filepath:
                return None
        return filepath

    def _launch_subprocess(self, filepath, poll=False, interval_ms=1000):
        """Launch ASE GUI as subprocess"""
        if not ASE_AVAILABLE:
            return

        filepath = str(Path(filepath).resolve())
        working_dir = str(Path(filepath).parent)

        if poll:
            script = SCRIPT_DIR / "poll_viewer.py"
            cmd = [sys.executable, str(script), filepath, str(interval_ms)]
        else:
            cmd = [sys.executable, "-m", "ase", "gui", filepath]

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=working_dir
        )
        self._polling = poll

        if self.on_file_opened:
            self.on_file_opened(filepath)

    def refresh_viewer(self):
        """Refresh by reopening with current file"""
        if self.current_filepath is None:
            print("No file opened yet")
            return
        if not os.path.exists(self.current_filepath):
            print(f"File not found: {self.current_filepath}")
            return
        self._launch_subprocess(self.current_filepath, poll=self._polling)
