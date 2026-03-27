"""Command parser"""
import shlex
from typing import List
from console.commands import CommandRegistry


class Parser:
    def __init__(self, controller):
        self.controller = controller
        self.registry = CommandRegistry(controller)
    
    def parse(self, command_line: str):
        """Parse and execute command"""
        if not command_line.strip():
            return
        
        try:
            parts = shlex.split(command_line)
        except ValueError as e:
            print(f"Parse error: {e}")
            return
        
        if not parts:
            return
        
        cmd = parts[0].lower()
        args = parts[1:]
        
        self.registry.execute(cmd, args)
