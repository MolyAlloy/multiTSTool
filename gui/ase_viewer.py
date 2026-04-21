"""ASE viewer integration"""
import tkinter as tk
from tkinter import ttk
import subprocess
import sys
import os
from pathlib import Path
import json
import tempfile

try:
    from ase.io import read
    ASE_AVAILABLE = True
except ImportError:
    ASE_AVAILABLE = False

SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
COMMAND_FILE = Path(tempfile.gettempdir()) / "ase_gui_commands.json"


class ASEViewer(ttk.Frame):
    def __init__(self, parent, controller, on_file_opened=None):
        super().__init__(parent)
        self.controller = controller
        self.on_file_opened = on_file_opened
        self.current_filepath = None
        self._polling = False
        self._process = None
        self._create_widgets()

    def _create_widgets(self):
        view_frame = ttk.LabelFrame(self, text="3D Viewer", padding="5")
        view_frame.pack(fill=tk.BOTH, expand=True)

        if not ASE_AVAILABLE:
            ttk.Label(
                view_frame,
                text="ASE not available\nInstall: pip install ase"
            ).pack()
            return

        btn_frame = ttk.Frame(view_frame)
        btn_frame.pack(pady=10)

        ttk.Button(
            btn_frame,
            text="Open ASE Viewer",
            command=self.open_ase_viewer
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Open + Poll",
            command=self.open_with_poll
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Atom Swap Mode",
            command=self.open_atom_swap_viewer
        ).pack(side=tk.LEFT, padx=5)

        self.poll_label = ttk.Label(view_frame, text="Polling: OFF")
        self.poll_label.pack(anchor=tk.W, pady=2)

        swap_frame = ttk.LabelFrame(view_frame, text="Quick Swap (when ASE open)", padding="5")
        swap_frame.pack(fill=tk.X, pady=(10, 0))

        swap_btn_frame = ttk.Frame(swap_frame)
        swap_btn_frame.pack()

        ttk.Label(swap_btn_frame, text="Atom 1:").pack(side=tk.LEFT, padx=2)
        self.atom1_entry = ttk.Entry(swap_btn_frame, width=6)
        self.atom1_entry.pack(side=tk.LEFT, padx=2)
        self.atom1_entry.insert(0, "0")

        ttk.Label(swap_btn_frame, text="Atom 2:").pack(side=tk.LEFT, padx=2)
        self.atom2_entry = ttk.Entry(swap_btn_frame, width=6)
        self.atom2_entry.pack(side=tk.LEFT, padx=2)
        self.atom2_entry.insert(0, "1")

        ttk.Button(
            swap_btn_frame,
            text="Swap Numbers",
            command=self.send_swap_command
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            swap_btn_frame,
            text="Get Selection",
            command=self.send_get_selection_command
        ).pack(side=tk.LEFT, padx=2)

        self.selection_label = ttk.Label(swap_frame, text="Selection: -")
        self.selection_label.pack(anchor=tk.W, pady=(5, 0))

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
        cmd = [sys.executable, str(script), filepath]
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self._polling = False
        self.poll_label.config(text="Atom Swap Mode: ON")
        if self.on_file_opened:
            self.on_file_opened(filepath)

    def send_swap_command(self):
        """Send swap command to running ASE GUI"""
        try:
            atom1 = int(self.atom1_entry.get())
            atom2 = int(self.atom2_entry.get())
        except ValueError:
            print("Invalid atom index")
            return

        self._write_command("swap", [atom1, atom2])
        print(f"Sent swap command: atoms {atom1} <-> {atom2}")

    def send_get_selection_command(self):
        """Request current selection from ASE GUI"""
        self._write_command("get_selection", None)

    def _write_command(self, cmd, indices):
        """Write command to the command file"""
        with open(COMMAND_FILE, "w") as f:
            json.dump({"cmd": cmd, "indices": indices}, f)

    def check_selection_response(self):
        """Poll for selection response from ASE GUI"""
        pass

    def _get_filepath(self):
        """Get file path from controller or file dialog"""
        filepath = self.controller.get_current_filepath()
        if filepath is None:
            from tkinter import filedialog
            filepath = filedialog.askopenfilename(
                title="Select file to open",
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

        if poll:
            script = SCRIPT_DIR / "poll_viewer.py"
            cmd = [sys.executable, str(script), filepath, str(interval_ms)]
            self.poll_label.config(text=f"Polling: ON")
        else:
            cmd = ["ase", "gui", filepath]
            self.poll_label.config(text="Polling: OFF")

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
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
