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

        self.poll_label = ttk.Label(view_frame, text="Polling: OFF")
        self.poll_label.pack(anchor=tk.W, pady=2)

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
