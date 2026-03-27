"""Application state management"""
from typing import Any, Optional


class AppState:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self.current_structure = None
        self.current_filepath = None
        self.selected_atoms = []
        self.history = []
        self.modified = False
        self._initialized = True
    
    def reset(self):
        """Reset state to initial"""
        self.current_structure = None
        self.current_filepath = None
        self.selected_atoms = []
        self.history = []
        self.modified = False
