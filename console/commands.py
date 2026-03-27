"""Command registry and implementations"""
from typing import Dict, Callable, Any, List


class CommandRegistry:
    def __init__(self, controller):
        self.controller = controller
        self.commands: Dict[str, Callable] = {}
        self._register_commands()
    
    def _register_commands(self):
        self.commands = {
            'help': self.cmd_help,
            'load': self.cmd_load,
            'save': self.cmd_save,
            'exit': self.cmd_exit,
            'quit': self.cmd_exit,
            'list': self.cmd_list,
            'select': self.cmd_select,
            'translate': self.cmd_translate,
            'rotate': self.cmd_rotate,
            'undo': self.cmd_undo,
            'redo': self.cmd_redo,
            'info': self.cmd_info,
        }
    
    def execute(self, cmd: str, args: List[str]):
        """Execute a command"""
        if cmd in self.commands:
            try:
                self.commands[cmd](args)
            except Exception as e:
                print(f"Error: {e}")
        else:
            print(f"Unknown command: {cmd}")
    
    def cmd_help(self, args: List[str]):
        """Show help"""
        print("Available commands:")
        for name in sorted(self.commands.keys()):
            print(f"  {name}")
    
    def cmd_load(self, args: List[str]):
        """Load structure file"""
        if not args:
            print("Usage: load <filepath>")
            return
        print(f"Loading {args[0]}...")
    
    def cmd_save(self, args: List[str]):
        """Save structure file"""
        if not args:
            print("Usage: save <filepath>")
            return
        print(f"Saving to {args[0]}...")
    
    def cmd_exit(self, args: List[str]):
        """Exit application"""
        print("Goodbye!")
        exit(0)
    
    def cmd_list(self, args: List[str]):
        """List atoms"""
        print("No structure loaded")
    
    def cmd_select(self, args: List[str]):
        """Select atoms"""
        print("Select command")
    
    def cmd_translate(self, args: List[str]):
        """Translate atoms"""
        print("Translate command")
    
    def cmd_rotate(self, args: List[str]):
        """Rotate atoms"""
        print("Rotate command")
    
    def cmd_undo(self, args: List[str]):
        """Undo last action"""
        print("Undo command")
    
    def cmd_redo(self, args: List[str]):
        """Redo last action"""
        print("Redo command")
    
    def cmd_info(self, args: List[str]):
        """Show structure info"""
        print("No structure loaded")
