"""Main control window"""
import tkinter as tk
from tkinter import ttk, scrolledtext
import fnmatch
import os
import shlex
import subprocess
import sys
import shutil
from pathlib import Path
import threading


class ControlWindow:
    SCRIPT_DIR = Path(__file__).parent.parent / "scripts"
    BUILTIN_COMMANDS = (
        "help", "scripts", "ase", "clear",
        "cd", "pwd", "ls", "dir", "ll",
        "cat", "head", "tail", "cp", "mv", "mkdir", "touch", "rm",
        "grep", "find", "tree", "less", "wc", "du", "df", "which", "echo",
    )
    
    def __init__(self, controller):
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("multiTS - VASP Structure Tool")
        self.root.geometry("900x720")
        
        self.history = []
        self.history_index = -1
        
        self._setup_ui()
    
    def _setup_ui(self):
        self.main_frame = ttk.Frame(self.root, padding="5")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        self._create_terminal()
        self._create_file_browser()
        self._create_main_area()
    
    def _create_terminal(self):
        terminal_frame = ttk.LabelFrame(self.main_frame, text="Terminal", padding="5")
        terminal_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        terminal_tools = ttk.Frame(terminal_frame)
        terminal_tools.pack(fill=tk.X, pady=(0, 5))

        ttk.Button(terminal_tools, text="Scripts", command=self.list_scripts).pack(side=tk.LEFT, padx=2)
        ttk.Button(
            terminal_tools,
            text="Clear",
            command=lambda: self.terminal.delete("1.0", tk.END)
        ).pack(side=tk.LEFT, padx=2)
        
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
        input_entry.bind("<Tab>", self._on_tab_complete)
        
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
        except OSError as e:
            self.file_list.insert(tk.END, f"[Cannot read directory: {e}]")
    
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
        parts = self._parse_command(cmd)
        if not parts:
            return
        
        command = parts[0].lower()
        args = parts[1:]
        
        if command == "help":
            self._print_output("Available commands:")
            self._print_output("  help     - Show this help message")
            self._print_output("  scripts  - List available VTST scripts")
            self._print_output("  ase      - Launch ASE GUI")
            self._print_output("  clear    - Clear terminal")
            self._print_output("  pwd      - Show current directory")
            self._print_output("  cd PATH  - Change current directory")
            self._print_output("  ls [PATH] / dir [PATH] / ll [PATH] - List files")
            self._print_output("  cat/head/tail/less FILE - View text files")
            self._print_output("  cp/mv/mkdir/touch/rm     - Basic file operations")
            self._print_output("  grep/find/tree/wc/du/df/which/echo - Common utilities")
            self._print_output("  Tab      - Complete commands, scripts, and paths")
            self._print_output("  <script> - Run a VTST script by name")
            self._print_output("  <system> - Run a system shell command")
        elif command == "scripts":
            self.list_scripts()
        elif command == "ase":
            self.launch_ase_gui()
        elif command == "clear":
            self.terminal.delete("1.0", tk.END)
        elif command == "pwd":
            self._cmd_pwd()
        elif command == "cd":
            self._cmd_cd(args)
        elif command in ("ls", "dir", "ll"):
            self._cmd_ls(args, long_format=(command == "ll"))
        elif command == "cat":
            self._cmd_cat(args)
        elif command == "head":
            self._cmd_head_tail(args, head=True)
        elif command == "tail":
            self._cmd_head_tail(args, head=False)
        elif command == "less":
            self._cmd_less(args)
        elif command == "cp":
            self._cmd_cp(args)
        elif command == "mv":
            self._cmd_mv(args)
        elif command == "mkdir":
            self._cmd_mkdir(args)
        elif command == "touch":
            self._cmd_touch(args)
        elif command == "rm":
            self._cmd_rm(args)
        elif command == "echo":
            self._cmd_echo(args)
        elif command == "grep":
            self._cmd_grep(args)
        elif command == "find":
            self._cmd_find(args)
        elif command == "tree":
            self._cmd_tree(args)
        elif command == "wc":
            self._cmd_wc(args)
        elif command == "du":
            self._cmd_du(args)
        elif command == "df":
            self._cmd_df(args)
        elif command == "which":
            self._cmd_which(args)
        else:
            script_name = parts[0]
            
            if script_name in self._get_script_names():
                self._run_script(script_name, args)
            else:
                self._run_system_command(cmd)
    
    def _parse_command(self, cmd):
        try:
            if os.name == "nt":
                lexer = shlex.shlex(cmd, posix=False)
                lexer.whitespace_split = True
                lexer.commenters = ""
                return [part.strip("\"'") for part in lexer]
            return shlex.split(cmd)
        except ValueError as e:
            self._print_output(f"Parse error: {e}", "error")
            return []
    
    def _cmd_pwd(self):
        self._print_output(str(self.current_path), "info")
    
    def _cmd_cd(self, args):
        if len(args) > 1:
            self._print_output("Usage: cd [path]", "error")
            return
        
        target = Path.home() if not args else Path(args[0]).expanduser()
        if not target.is_absolute():
            target = self.current_path / target
        
        try:
            target = target.resolve()
        except OSError as e:
            self._print_output(f"cd: {e}", "error")
            return
        
        if not target.exists():
            self._print_output(f"cd: no such directory: {target}", "error")
            return
        if not target.is_dir():
            self._print_output(f"cd: not a directory: {target}", "error")
            return
        
        self._navigate_to(target)
        self._print_output(str(self.current_path), "info")
    
    def _cmd_ls(self, args, long_format=False):
        show_hidden = False
        targets = []
        
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                show_hidden = show_hidden or "a" in arg
                long_format = long_format or "l" in arg
            else:
                targets.append(arg)
        
        if len(targets) > 1:
            self._print_output("Usage: ls [-a] [-l] [path]", "error")
            return
        
        target = Path(targets[0]).expanduser() if targets else self.current_path
        if not target.is_absolute():
            target = self.current_path / target
        
        try:
            target = target.resolve()
        except OSError as e:
            self._print_output(f"ls: {e}", "error")
            return
        
        if not target.exists():
            self._print_output(f"ls: no such file or directory: {target}", "error")
            return
        
        if target.is_file():
            self._print_output(self._format_ls_item(target, long_format))
            return
        
        try:
            entries = [
                item for item in target.iterdir()
                if show_hidden or not item.name.startswith(".")
            ]
        except PermissionError:
            self._print_output(f"ls: permission denied: {target}", "error")
            return
        
        entries.sort(key=lambda item: (not item.is_dir(), item.name.lower()))
        if not entries:
            return
        
        if long_format:
            self._print_output("\n".join(self._format_ls_item(item, True) for item in entries))
        else:
            self._print_output("  ".join(self._format_ls_item(item, False) for item in entries))
    
    def _format_ls_item(self, path, long_format):
        suffix = os.sep if path.is_dir() else ""
        if not long_format:
            return f"{path.name}{suffix}"
        
        kind = "<DIR>" if path.is_dir() else "     "
        size = "" if path.is_dir() else str(path.stat().st_size)
        return f"{kind:>5} {size:>10} {path.name}{suffix}"
    
    def _resolve_path(self, value):
        path = Path(value).expanduser()
        if not path.is_absolute():
            path = self.current_path / path
        return path.resolve()
    
    def _read_text_lines(self, path):
        try:
            return path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as e:
            self._print_output(f"{path.name}: {e}", "error")
            return None
    
    def _cmd_cat(self, args):
        if not args:
            self._print_output("Usage: cat <file> [file ...]", "error")
            return
        
        output = []
        for arg in args:
            path = self._resolve_path(arg)
            if not path.is_file():
                self._print_output(f"cat: not a file: {path}", "error")
                continue
            lines = self._read_text_lines(path)
            if lines is not None:
                output.append("\n".join(lines))
        
        if output:
            self._print_output("\n".join(output))
    
    def _cmd_less(self, args):
        if not args:
            self._print_output("Usage: less <file>", "error")
            return
        self._print_output("less: interactive paging is not supported; showing file content.", "info")
        self._cmd_cat(args)
    
    def _cmd_head_tail(self, args, head=True):
        count = 10
        files = []
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "-n":
                if index + 1 >= len(args):
                    self._print_output("Usage: head/tail [-n N] <file> [file ...]", "error")
                    return
                try:
                    count = max(0, int(args[index + 1]))
                except ValueError:
                    self._print_output(f"Invalid line count: {args[index + 1]}", "error")
                    return
                index += 2
            elif arg.startswith("-n") and len(arg) > 2:
                try:
                    count = max(0, int(arg[2:]))
                except ValueError:
                    self._print_output(f"Invalid line count: {arg}", "error")
                    return
                index += 1
            else:
                files.append(arg)
                index += 1
        
        if not files:
            self._print_output("Usage: head/tail [-n N] <file> [file ...]", "error")
            return
        
        chunks = []
        for name in files:
            path = self._resolve_path(name)
            if not path.is_file():
                self._print_output(f"{'head' if head else 'tail'}: not a file: {path}", "error")
                continue
            lines = self._read_text_lines(path)
            if lines is None:
                continue
            selected = lines[:count] if head else lines[-count:] if count else []
            if len(files) > 1:
                chunks.append(f"==> {path.name} <==")
            chunks.append("\n".join(selected))
        
        if chunks:
            self._print_output("\n".join(chunks))
    
    def _cmd_cp(self, args):
        recursive = False
        operands = []
        for arg in args:
            if arg in ("-r", "-R", "--recursive"):
                recursive = True
            else:
                operands.append(arg)
        
        if len(operands) != 2:
            self._print_output("Usage: cp [-r] <source> <dest>", "error")
            return
        
        source = self._resolve_path(operands[0])
        dest = self._resolve_path(operands[1])
        if not source.exists():
            self._print_output(f"cp: no such file or directory: {source}", "error")
            return
        
        try:
            if source.is_dir():
                if not recursive:
                    self._print_output(f"cp: {source} is a directory; use -r", "error")
                    return
                final_dest = dest / source.name if dest.exists() and dest.is_dir() else dest
                shutil.copytree(source, final_dest)
            else:
                final_dest = dest / source.name if dest.exists() and dest.is_dir() else dest
                final_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, final_dest)
            self._print_output(f"Copied: {source} -> {final_dest}", "info")
            self._refresh_file_list()
        except OSError as e:
            self._print_output(f"cp: {e}", "error")
    
    def _cmd_mv(self, args):
        if len(args) != 2:
            self._print_output("Usage: mv <source> <dest>", "error")
            return
        
        source = self._resolve_path(args[0])
        dest = self._resolve_path(args[1])
        if not source.exists():
            self._print_output(f"mv: no such file or directory: {source}", "error")
            return
        
        try:
            final_dest = dest / source.name if dest.exists() and dest.is_dir() else dest
            final_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(final_dest))
            self._print_output(f"Moved: {source} -> {final_dest}", "info")
            self._refresh_file_list()
        except OSError as e:
            self._print_output(f"mv: {e}", "error")
    
    def _cmd_mkdir(self, args):
        parents = False
        paths = []
        for arg in args:
            if arg == "-p":
                parents = True
            else:
                paths.append(arg)
        
        if not paths:
            self._print_output("Usage: mkdir [-p] <dir> [dir ...]", "error")
            return
        
        for name in paths:
            path = self._resolve_path(name)
            try:
                path.mkdir(parents=parents, exist_ok=parents)
                self._print_output(f"Created directory: {path}", "info")
            except OSError as e:
                self._print_output(f"mkdir: {e}", "error")
        self._refresh_file_list()
    
    def _cmd_touch(self, args):
        if not args:
            self._print_output("Usage: touch <file> [file ...]", "error")
            return
        
        for name in args:
            path = self._resolve_path(name)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.touch(exist_ok=True)
                self._print_output(f"Touched: {path}", "info")
            except OSError as e:
                self._print_output(f"touch: {e}", "error")
        self._refresh_file_list()
    
    def _cmd_rm(self, args):
        recursive = False
        force = False
        targets = []
        for arg in args:
            if arg in ("-r", "-R", "--recursive"):
                recursive = True
            elif arg in ("-f", "--force"):
                force = True
            elif arg in ("-rf", "-fr"):
                recursive = True
                force = True
            else:
                targets.append(arg)
        
        if not targets:
            self._print_output("Usage: rm [-r] [-f] <path> [path ...]", "error")
            return
        
        for name in targets:
            path = self._resolve_path(name)
            if not path.exists():
                if not force:
                    self._print_output(f"rm: no such file or directory: {path}", "error")
                continue
            try:
                if path.is_dir():
                    if not recursive:
                        self._print_output(f"rm: {path} is a directory; use -r", "error")
                        continue
                    shutil.rmtree(path)
                else:
                    path.unlink()
                self._print_output(f"Removed: {path}", "info")
                if not self.current_path.exists():
                    fallback = path.parent if path.parent.exists() else Path.cwd()
                    self.current_path = fallback
            except OSError as e:
                self._print_output(f"rm: {e}", "error")
        self._refresh_file_list()
    
    def _cmd_echo(self, args):
        self._print_output(" ".join(args))
    
    def _cmd_grep(self, args):
        ignore_case = False
        show_line_numbers = False
        operands = []
        for arg in args:
            if arg.startswith("-") and len(arg) > 1:
                ignore_case = ignore_case or "i" in arg
                show_line_numbers = show_line_numbers or "n" in arg
            else:
                operands.append(arg)
        
        if len(operands) < 2:
            self._print_output("Usage: grep [-i] [-n] <pattern> <file> [file ...]", "error")
            return
        
        pattern = operands[0]
        needle = pattern.lower() if ignore_case else pattern
        matches = []
        multiple_files = len(operands) > 2
        for name in operands[1:]:
            path = self._resolve_path(name)
            if not path.is_file():
                self._print_output(f"grep: not a file: {path}", "error")
                continue
            lines = self._read_text_lines(path)
            if lines is None:
                continue
            for line_no, line in enumerate(lines, start=1):
                haystack = line.lower() if ignore_case else line
                if needle in haystack:
                    prefix = ""
                    if multiple_files:
                        prefix += f"{path.name}:"
                    if show_line_numbers:
                        prefix += f"{line_no}:"
                    matches.append(f"{prefix}{line}")
        
        if matches:
            self._print_output("\n".join(matches))
    
    def _cmd_find(self, args):
        root_arg = "."
        name_pattern = None
        type_filter = None
        index = 0
        
        if args and not args[0].startswith("-"):
            root_arg = args[0]
            index = 1
        
        while index < len(args):
            arg = args[index]
            if arg == "-name" and index + 1 < len(args):
                name_pattern = args[index + 1]
                index += 2
            elif arg == "-type" and index + 1 < len(args):
                type_filter = args[index + 1]
                if type_filter not in ("f", "d"):
                    self._print_output("find: -type must be f or d", "error")
                    return
                index += 2
            else:
                self._print_output("Usage: find [path] [-name pattern] [-type f|d]", "error")
                return
        
        root = self._resolve_path(root_arg)
        if not root.exists():
            self._print_output(f"find: no such file or directory: {root}", "error")
            return
        
        results = []
        try:
            iterator = [root] if root.is_file() else root.rglob("*")
            for path in iterator:
                if type_filter == "f" and not path.is_file():
                    continue
                if type_filter == "d" and not path.is_dir():
                    continue
                if name_pattern and not fnmatch.fnmatch(path.name, name_pattern):
                    continue
                results.append(str(path.relative_to(self.current_path) if path.is_relative_to(self.current_path) else path))
        except OSError as e:
            self._print_output(f"find: {e}", "error")
            return
        
        if results:
            self._print_output("\n".join(results))
    
    def _cmd_tree(self, args):
        max_depth = 2
        target_arg = "."
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "-L" and index + 1 < len(args):
                try:
                    max_depth = max(0, int(args[index + 1]))
                except ValueError:
                    self._print_output(f"tree: invalid depth: {args[index + 1]}", "error")
                    return
                index += 2
            elif not arg.startswith("-"):
                target_arg = arg
                index += 1
            else:
                self._print_output("Usage: tree [-L depth] [path]", "error")
                return
        
        root = self._resolve_path(target_arg)
        if not root.is_dir():
            self._print_output(f"tree: not a directory: {root}", "error")
            return
        
        lines = [root.name + os.sep]
        
        def walk(path, prefix, depth):
            if depth >= max_depth:
                return
            try:
                children = sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
            except PermissionError:
                lines.append(prefix + "[permission denied]")
                return
            for index, child in enumerate(children):
                connector = "`-- " if index == len(children) - 1 else "|-- "
                lines.append(prefix + connector + child.name + (os.sep if child.is_dir() else ""))
                if child.is_dir():
                    extension = "    " if index == len(children) - 1 else "|   "
                    walk(child, prefix + extension, depth + 1)
        
        walk(root, "", 0)
        self._print_output("\n".join(lines))
    
    def _cmd_wc(self, args):
        if not args:
            self._print_output("Usage: wc <file> [file ...]", "error")
            return
        
        lines = []
        totals = [0, 0, 0]
        for name in args:
            path = self._resolve_path(name)
            if not path.is_file():
                self._print_output(f"wc: not a file: {path}", "error")
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            counts = [text.count("\n"), len(text.split()), len(text.encode("utf-8"))]
            totals = [left + right for left, right in zip(totals, counts)]
            lines.append(f"{counts[0]:8} {counts[1]:8} {counts[2]:8} {path.name}")
        if len(lines) > 1:
            lines.append(f"{totals[0]:8} {totals[1]:8} {totals[2]:8} total")
        if lines:
            self._print_output("\n".join(lines))
    
    def _cmd_du(self, args):
        targets = args or ["."]
        lines = []
        for name in targets:
            path = self._resolve_path(name)
            if not path.exists():
                self._print_output(f"du: no such file or directory: {path}", "error")
                continue
            total = self._path_size(path)
            lines.append(f"{self._format_bytes(total):>10} {path}")
        if lines:
            self._print_output("\n".join(lines))
    
    def _path_size(self, path):
        if path.is_file():
            return path.stat().st_size
        total = 0
        for item in path.rglob("*"):
            try:
                if item.is_file():
                    total += item.stat().st_size
            except OSError:
                pass
        return total
    
    def _format_bytes(self, size):
        value = float(size)
        for unit in ("B", "K", "M", "G", "T"):
            if value < 1024 or unit == "T":
                return f"{value:.1f}{unit}" if unit != "B" else f"{int(value)}B"
            value /= 1024
        return f"{size}B"
    
    def _cmd_df(self, args):
        target = self._resolve_path(args[0]) if args else self.current_path
        try:
            usage = shutil.disk_usage(target)
        except OSError as e:
            self._print_output(f"df: {e}", "error")
            return
        used = usage.total - usage.free
        percent = (used / usage.total * 100) if usage.total else 0
        self._print_output(
            "Filesystem      Size      Used     Avail Use%\n"
            f"{target.anchor or target} {self._format_bytes(usage.total):>9} "
            f"{self._format_bytes(used):>9} {self._format_bytes(usage.free):>9} {percent:>3.0f}%"
        )
    
    def _cmd_which(self, args):
        if not args:
            self._print_output("Usage: which <command> [command ...]", "error")
            return
        
        script_names = set(self._get_script_names())
        lines = []
        for name in args:
            if name in self.BUILTIN_COMMANDS:
                lines.append(f"{name}: builtin")
            elif name in script_names:
                lines.append(str(self.SCRIPT_DIR / f"{name}.py"))
            else:
                found = shutil.which(name)
                if found:
                    lines.append(found)
                else:
                    self._print_output(f"{name} not found", "error")
        if lines:
            self._print_output("\n".join(lines))
    
    def _on_tab_complete(self, event):
        text = self.input_var.get()
        cursor = event.widget.index(tk.INSERT)
        start, token, is_first_token = self._completion_context(text, cursor)
        candidates = self._completion_candidates(token, is_first_token)
        
        if not candidates:
            return "break"
        
        if len(candidates) == 1:
            replacement = candidates[0]
            if is_first_token:
                replacement += " "
            self._replace_input_range(event.widget, start, cursor, replacement)
            return "break"
        
        common = os.path.commonprefix(candidates)
        if common and common != token:
            self._replace_input_range(event.widget, start, cursor, common)
        
        self._print_output("  ".join(candidates), "info")
        return "break"
    
    def _completion_context(self, text, cursor):
        prefix = text[:cursor]
        start = max(prefix.rfind(" "), prefix.rfind("\t")) + 1
        token = prefix[start:]
        is_first_token = not prefix[:start].strip()
        return start, token, is_first_token
    
    def _completion_candidates(self, token, is_first_token):
        if is_first_token:
            names = sorted(set(self.BUILTIN_COMMANDS) | set(self._get_script_names()))
            token_lower = token.lower()
            return [name for name in names if name.lower().startswith(token_lower)]
        
        return self._path_completion_candidates(token)
    
    def _path_completion_candidates(self, token):
        quote = token[0] if token.startswith(("'", '"')) else ""
        raw = token[1:] if quote else token
        expanded = Path(raw).expanduser() if raw else Path()
        ends_with_sep = raw.endswith(("/", "\\"))
        
        if raw and (expanded.is_absolute() or expanded.drive):
            search_dir = expanded if ends_with_sep else expanded.parent
            name_prefix = "" if ends_with_sep else expanded.name
            visible_prefix = str(search_dir) if ends_with_sep else str(expanded.parent)
        else:
            relative = Path(raw)
            search_dir = self.current_path / relative if ends_with_sep else self.current_path / relative.parent
            name_prefix = "" if ends_with_sep else relative.name
            visible_prefix = str(relative) if ends_with_sep else str(relative.parent)
            if visible_prefix == ".":
                visible_prefix = ""
        
        try:
            children = list(search_dir.iterdir())
        except OSError:
            return []
        
        matches = []
        include_hidden = name_prefix.startswith(".")
        for child in sorted(children, key=lambda item: (not item.is_dir(), item.name.lower())):
            if not include_hidden and child.name.startswith("."):
                continue
            if not child.name.lower().startswith(name_prefix.lower()):
                continue
            
            name = child.name + (os.sep if child.is_dir() else "")
            completed = str(Path(visible_prefix) / name) if visible_prefix else name
            if quote or any(char.isspace() for char in completed):
                completed = f'"{completed}"'
            matches.append(completed)
        
        return matches
    
    def _replace_input_range(self, entry, start, end, replacement):
        entry.delete(start, end)
        entry.insert(start, replacement)
        entry.icursor(start + len(replacement))
    
    def _get_script_names(self):
        scripts = []
        if self.SCRIPT_DIR.exists():
            for f in self.SCRIPT_DIR.glob("*.py"):
                if f.stem != "__init__":
                    scripts.append(f.stem)
        return scripts
    
    def list_scripts(self):
        scripts = self._get_script_names()
        self._print_output("Available scripts:", "info")
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
            on_file_opened=self._on_file_opened,
            open_command=self.open_file,
            save_command=self.save_file,
            cp2k_fix_command=self.launch_cp2k_fix_gui
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
            initialdir=str(self.current_path),
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
        file_path = Path(filepath).resolve()
        self._print_output(f"Opening: {file_path}", "info")
        
        def run_ase_gui():
            import subprocess
            import sys
            
            subprocess.Popen(
                [sys.executable, "-m", "ase", "gui", str(file_path)],
                cwd=str(file_path.parent)
            )
            
            self.terminal.after(0, lambda: self._print_output("ASE GUI launched", "info"))
        
        threading.Thread(target=run_ase_gui, daemon=True).start()
    
    def save_file(self):
        from tkinter import filedialog
        current = self.controller.get_current_filepath()
        if not current:
            self._print_output("No structure file is currently open.", "error")
            return

        current_path = Path(current).resolve()
        filepath = filedialog.asksaveasfilename(
            initialdir=str(current_path.parent),
            initialfile=current_path.name,
            filetypes=[("XYZ files", "*.xyz"), ("VASP files", "*.vasp"), ("All files", "*.*")]
        )
        if not filepath:
            return

        target_path = Path(filepath).resolve()
        try:
            if target_path == current_path:
                self._print_output(f"Already saved: {target_path}", "info")
                return

            try:
                from ase.io import read, write
                atoms = read(str(current_path))
                write(str(target_path), atoms)
            except Exception:
                shutil.copy2(current_path, target_path)

            self.controller.set_current_filepath(str(target_path))
            self._print_output(f"Saved: {target_path}", "info")
            self._navigate_to(target_path.parent)
        except Exception as e:
            self._print_output(f"Error saving file: {e}", "error")
    
    def save_as(self):
        self.save_file()
    
    def launch_ase_gui(self):
        self._print_output("Launching ASE GUI...", "info")
        try:
            subprocess.Popen([sys.executable, "-m", "ase", "gui"], cwd=str(self.current_path))
        except FileNotFoundError:
            self._print_output("Error: 'ase gui' command not found. Make sure ASE is installed.", "error")

    def launch_cp2k_fix_gui(self):
        from tkinter import filedialog

        filepath = filedialog.askopenfilename(
            title="Select structure file for CP2K fixed atoms",
            initialdir=str(self.current_path),
            filetypes=[
                ("Structure files", "*.xyz *.vasp *.cif CONTCAR POSCAR"),
                ("All files", "*.*")
            ]
        )
        if not filepath:
            return

        script = self.SCRIPT_DIR / "cp2k_fix_viewer.py"
        if not script.exists():
            self._print_output(f"Script not found: {script}", "error")
            return

        self._print_output(f"Launching CP2K-FIX: {filepath}", "info")
        self.controller.set_current_filepath(filepath)

        file_path = Path(filepath)
        if file_path.exists():
            self._navigate_to(file_path.parent)

        try:
            subprocess.Popen([sys.executable, str(script), filepath], cwd=str(file_path.parent))
            self._print_output("CP2K-FIX launched", "info")
        except Exception as e:
            self._print_output(f"Error launching CP2K-FIX: {e}", "error")
    
    def undo(self):
        print("Undo")
    
    def redo(self):
        print("Redo")
    
    def run(self):
        self.root.mainloop()
