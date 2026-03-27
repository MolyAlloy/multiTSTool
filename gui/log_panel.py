"""Log panel for GUI"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import logging


class LogPanel(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self._create_widgets()
        self._setup_logging()
    
    def _create_widgets(self):
        log_frame = ttk.LabelFrame(self, text="Log", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, wrap=tk.WORD, state=tk.DISABLED
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        btn_frame = ttk.Frame(log_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(btn_frame, text="Clear", command=self.clear).pack(side=tk.RIGHT)
    
    def _setup_logging(self):
        self.handler = TextHandler(self)
        logging.getLogger().addHandler(self.handler)
        logging.getLogger().setLevel(logging.INFO)
    
    def append(self, message: str):
        """Append message to log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
    
    def clear(self):
        """Clear log"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)


class TextHandler(logging.Handler):
    def __init__(self, panel: LogPanel):
        super().__init__()
        self.panel = panel
    
    def emit(self, record):
        msg = self.format(record)
        self.panel.append(msg)
