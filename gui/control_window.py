"""Main control window"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import subprocess
import sys
import os
from pathlib import Path
import threading


class ControlWindow:
    SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
    
    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("multiTS - VASP Structure Tool")
        self.root.geometry("900x600")
        
        self.history = []
        self.history_index = -1
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.main_frame = ttk.Frame(self.root, padding="5")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_toolbar()
        self._create_menu()
        self._create_terminal()
        self._create_file_browser()
        self._create_main_area()
    
    def _create_toolbar(self):
        toolbar = ttk.Frame(self.main_frame)
        toolbar.pack(side=tk.TOP, fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="Open", command=self.open_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save", command=self.save_file).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save As...", command=self.save_as).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="ASE GUI", command=self.launch_ase_gui).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=5)
        ttk.Button(toolbar, text="Scripts", command=self.list_scripts).pack(side=tk.LEFT, padx=2)
    
    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Structure...", command=self.open_file)
        file_menu.add_command(label="Save", command=self.save_file)
        file_menu.add_command(label="Save As...", command=self.save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        
        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Tools", menu=tools_menu)
        tools_menu.add_command(label="Open ASE GUI", command=self.launch_ase_gui)
        tools_menu.add_command(label="Refresh Scripts", command=self.list_scripts)
    
    def _create_terminal(self):
        terminal_frame = ttk.LabelFrame(self.main_frame, text="Terminal", padding="5")
        terminal_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        
        self.terminal = scrolledtext.ScrolledText(
            terminal_frame, 
            height=12, 
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white"
        )
        self.terminal.pack(fill=tk.BOTH, expand=True)
        self.terminal.tag_config("prompt", foreground="#569cd6")
        self.terminal.tag_config("output", foreground="#d4d4d4")
        self.terminal.tag_config("error", foreground="#f44747")
        self.terminal.tag_config("info", foreground="#6a9955")
        
        self.input_var = tk.StringVar()
        input_entry = ttk.Entry(terminal_frame, textvariable=self.input_var, font=("Consolas", 10))
        input_entry.pack(fill=tk.X, pady=(5, 0))
        input_entry.bind("<Return>", self._on_enter_key)
        
        self.terminal.insert(tk.END, "multiTS terminal v0.1\n", "info")
        self.terminal.insert(tk.END, "Type 'help' for available commands\n", "info")
        self.terminal.insert(tk.END, "Type 'scripts' to list available scripts\n", "info")
        
        input_entry.focus_set()
    
    def _create_file_browser(self):
        browser_frame = ttk.LabelFrame(self.main_frame, text="File Browser", padding="5")
        browser_frame.pack(fill=tk.X, pady=(0, 5))
        
        toolbar = ttk.Frame(browser_frame)
        toolbar.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Button(toolbar, text="◀", width=3, command=self._go_back).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="▶", width=3, command=self._go_forward).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="⬆", width=3, command=self._go_up).pack(side=tk.LEFT, padx=2)
        
        self.path_var = tk.StringVar(value=str(Path.cwd()))
        path_entry = ttk.Entry(toolbar, textvariable=self.path_var, font=("Consolas", 9))
        path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        path_entry.bind("<Return>", self._on_path_change)
        
        ttk.Button(toolbar, text="↻", width=3, command=self._refresh_browser).pack(side=tk.LEFT, padx=2)
        
        list_frame = ttk.Frame(browser_frame, height=180)
        list_frame.pack(fill=tk.BOTH, expand=True)
        list_frame.pack_propagate(False)
        
        self.file_list = tk.Listbox(list_frame, font=("Consolas", 9), height=10)
        self.file_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.file_list.bind("<Double-Button-1>", self._on_file_double_click)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_list.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_list.config(yscrollcommand=scrollbar.set)
        
        self.current_path = Path.cwd()
        self._refresh_file_list()
    
    def _refresh_file_list(self):
        self.file_list.delete(0, tk.END)
        self.path_var.set(str(self.current_path))
        
        try:
            dirs = sorted([d.name for d in self.current_path.iterdir() if d.is_dir() and not d.name.startswith('.')])
            files = sorted([f.name for f in self.current_path.iterdir() if f.is_file() and not f.name.startswith('.')])
            
            for d in dirs:
                self.file_list.insert(tk.END, f"[{d}]")
            for f in files:
                self.file_list.insert(tk.END, f)
        except PermissionError:
            self.file_list.insert(tk.END, "[Permission Denied]")
    
    def _on_file_double_click(self, event):
        selection = self.file_list.get(self.file_list.curselection())
        if selection.startswith("[") and selection.endswith("]"):
            new_path = self.current_path / selection[1:-1]
            if new_path.is_dir():
                self._navigate_to(new_path)
        else:
            filepath = self.current_path / selection
            if filepath.is_file():
                self._open_file(filepath)
    
    def _navigate_to(self, path):
        if path in self.history[:self.history_index + 1]:
            self.history_index = self.history.index(path)
        else:
            self.history = self.history[:self.history_index + 1]
            self.history.append(path)
            self.history_index += 1
        
        self.current_path = path
        self._refresh_file_list()
    
    def _go_back(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.current_path = self.history[self.history_index]
            self._refresh_file_list()
    
    def _go_forward(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.current_path = self.history[self.history_index]
            self._refresh_file_list()
    
    def _go_up(self):
        parent = self.current_path.parent
        if parent != self.current_path:
            self._navigate_to(parent)
    
    def _on_path_change(self, event):
        new_path = Path(self.path_var.get())
        if new_path.is_dir():
            self._navigate_to(new_path)
    
    def _refresh_browser(self):
        self._refresh_file_list()
    
    def _open_file(self, filepath):
        self.controller.set_current_filepath(str(filepath))
        self._open_in_ase(str(filepath))
    
    def _on_enter_key(self, event):
        line = self.input_var.get().strip()
        self.terminal.insert(tk.END, f">>> {line}\n")
        self.input_var.set("")
        self._execute_command(line)
        return "break"
    
    def _execute_command(self, cmd):
        if not cmd:
            return
        
        cmd = cmd.strip()
        
        if cmd == "help":
            self._print_output("Available commands:")
            self._print_output("  help     - Show this help message")
            self._print_output("  scripts  - List available VTST scripts")
            self._print_output("  ase      - Launch ASE GUI")
            self._print_output("  clear    - Clear terminal")
            self._print_output("  <script> - Run a VTST script by name")
        elif cmd == "scripts":
            self.list_scripts()
        elif cmd == "ase":
            self.launch_ase_gui()
        elif cmd == "clear":
            self.terminal.delete("1.0", tk.END)
        else:
            parts = cmd.split()
            script_name = parts[0]
            args = parts[1:] if len(parts) > 1 else []
            
            if script_name in self._get_script_names():
                self._run_script(script_name, args)
            else:
                self._run_system_command(cmd)
    
    def _get_script_names(self):
        scripts = []
        if self.SCRIPT_DIR.exists():
            for f in self.SCRIPT_DIR.glob("*.py"):
                if f.stem != "__init__":
                    scripts.append(f.stem)
        return scripts
    
    def list_scripts(self):
        scripts = self._get_script_names()
        self._print_output("Available VTST scripts:", "info")
        for s in scripts:
            self._print_output(f"  {s}")
        if not scripts:
            self._print_output("  No scripts found", "error")
    
    def _run_script(self, script_name, args=None):
        if args is None:
            args = []
        
        script_path = self.SCRIPT_DIR / f"{script_name}.py"
        if not script_path.exists():
            self._print_output(f"Script not found: {script_name}", "error")
            return
        
        self._print_output(f"Running {script_name} {' '.join(args)}...", "info")
        
        working_dir = str(self.current_path)
        
        def run():
            try:
                cmd = [sys.executable, str(script_path)] + args
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    cwd=working_dir
                )
                if result.stdout:
                    self.terminal.after(0, lambda: self._print_output(result.stdout))
                if result.stderr:
                    self.terminal.after(0, lambda: self._print_output(result.stderr, "error"))
                if result.returncode == 0:
                    self.terminal.after(0, lambda: self._print_output(f"[Done] {script_name} completed", "info"))
                else:
                    self.terminal.after(0, lambda: self._print_output(f"[Error] Exit code: {result.returncode}", "error"))
            except Exception as e:
                self.terminal.after(0, lambda: self._print_output(f"Error: {str(e)}", "error"))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _run_system_command(self, cmd):
        self._print_output(f"$ {cmd}")
        working_dir = str(self.current_path)
        
        def run():
            try:
                result = subprocess.run(
                    cmd, 
                    shell=True, 
                    capture_output=True, 
                    text=True,
                    cwd=working_dir
                )
                if result.stdout:
                    self.terminal.after(0, lambda: self._print_output(result.stdout))
                if result.stderr:
                    self.terminal.after(0, lambda: self._print_output(result.stderr, "error"))
            except Exception as e:
                self.terminal.after(0, lambda: self._print_output(f"Error: {str(e)}", "error"))
        
        threading.Thread(target=run, daemon=True).start()
    
    def _print_output(self, text, tag="output"):
        self.terminal.insert(tk.END, text + "\n", tag)
        self.terminal.see(tk.END)
    
    def _create_main_area(self):
        from gui.ase_viewer import ASEViewer
        self.ase_viewer = ASEViewer(
            self.main_frame,
            self.controller,
            on_file_opened=self._on_file_opened
        )
        self.ase_viewer.pack(fill=tk.BOTH, expand=True)

    def _on_file_opened(self, filepath):
        """Called when ASEViewer opens a file"""
        self.controller.set_current_filepath(filepath)
        file_path = Path(filepath)
        if file_path.exists():
            self._navigate_to(file_path.parent)
    
    def open_file(self):
        from tkinter import filedialog
        filepath = filedialog.askopenfilename(
            filetypes=[("Structure files", "*.xyz *.vasp *.cif"), ("All files", "*.*")]
        )
        if filepath:
            self._print_output(f"Opening: {filepath}", "info")
            self.controller.set_current_filepath(filepath)
            self._open_in_ase(filepath)
            file_path = Path(filepath)
            if file_path.exists():
                self._navigate_to(file_path.parent)
    
    def _open_in_ase(self, filepath):
        self._print_output(f"Opening: {filepath}", "info")
        
        def run_ase_gui():
            import subprocess
            import os
            import sys
            
            if sys.platform == "win32":
                cmd = f'start cmd /c "python -m ase gui {filepath}"'
                subprocess.run(cmd, shell=True)
            else:
                subprocess.Popen(["ase", "gui", filepath])
            
            self.terminal.after(0, lambda: self._print_output("ASE GUI launched", "info"))
        
        threading.Thread(target=run_ase_gui, daemon=True).start()
    
    def save_file(self):
        from tkinter import filedialog
        filepath = filedialog.asksaveasfilename(
            filetypes=[("XYZ files", "*.xyz"), ("VASP files", "*.vasp"), ("All files", "*.*")]
        )
        if filepath:
            print(f"Saving: {filepath}")
    
    def save_as(self):
        self.save_file()
    
    def launch_ase_gui(self):
        self._print_output("Launching ASE GUI...", "info")
        try:
            subprocess.Popen(["ase", "gui"])
        except FileNotFoundError:
            self._print_output("Error: 'ase gui' command not found. Make sure ASE is installed.", "error")
    
    def undo(self):
        print("Undo")
    
    def redo(self):
        print("Redo")
    
    def run(self):
        self.root.mainloop()
