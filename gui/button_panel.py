"""Button panel for GUI"""
import tkinter as tk
from tkinter import ttk


class ButtonPanel(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self._create_buttons()
    
    def _create_buttons(self):
        operations_frame = ttk.LabelFrame(self, text="Operations", padding="5")
        operations_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.buttons = {
            'translate': ttk.Button(operations_frame, text="Translate", command=self.translate),
            'rotate': ttk.Button(operations_frame, text="Rotate", command=self.rotate),
            'scale': ttk.Button(operations_frame, text="Scale", command=self.scale),
            'mirror': ttk.Button(operations_frame, text="Mirror", command=self.mirror),
            'delete': ttk.Button(operations_frame, text="Delete", command=self.delete_atoms),
        }
        
        for btn in self.buttons.values():
            btn.pack(fill=tk.X, pady=2)
    
    def translate(self):
        print("Translate")
    
    def rotate(self):
        print("Rotate")
    
    def scale(self):
        print("Scale")
    
    def mirror(self):
        print("Mirror")
    
    def delete_atoms(self):
        print("Delete atoms")
