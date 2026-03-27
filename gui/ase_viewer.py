"""ASE viewer integration"""
import tkinter as tk
from tkinter import ttk
try:
    from ase.visualize import view
    ASE_AVAILABLE = True
except ImportError:
    ASE_AVAILABLE = False


class ASEViewer(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
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
        
        ttk.Button(
            view_frame, 
            text="Open in ASE Viewer", 
            command=self.open_ase_viewer
        ).pack(pady=10)
        
        ttk.Label(view_frame, text="View settings:").pack(anchor=tk.W, pady=5)
        
        settings = ttk.Frame(view_frame)
        settings.pack(fill=tk.X)
        
        ttk.Label(settings, text="Rotation:").grid(row=0, column=0, sticky=tk.W)
        self.rotation = ttk.Entry(settings, width=10)
        self.rotation.insert(0, "0x")
        self.rotation.grid(row=0, column=1, padx=5, pady=2)
        
        ttk.Label(settings, text="Zoom:").grid(row=1, column=0, sticky=tk.W)
        self.zoom = ttk.Entry(settings, width=10)
        self.zoom.insert(0, "1.0")
        self.zoom.grid(row=1, column=1, padx=5, pady=2)
    
    def open_ase_viewer(self):
        """Open current structure in ASE viewer"""
        structure = self.controller.get_current_structure()
        if structure is None:
            print("No structure loaded")
            return
        
        if ASE_AVAILABLE:
            atoms = self._create_ase_atoms(structure)
            view(atoms)
    
    def _create_ase_atoms(self, structure):
        """Convert structure to ASE Atoms object"""
        from ase import Atoms
        symbols = structure.get('symbols', [])
        positions = structure.get('positions', [])
        cell = structure.get('cell')
        
        atoms = Atoms(symbols=symbols, positions=positions, pbc=True if cell else False)
        if cell is not None:
            atoms.set_cell(cell)
        
        return atoms
