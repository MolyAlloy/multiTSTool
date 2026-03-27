"""Configuration management"""
import os
from pathlib import Path


class Config:
    def __init__(self):
        self.home_dir = Path.home() / ".structool"
        self.plugins_dir = self.home_dir / "plugins"
        self.history_file = self.home_dir / "history.txt"
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        self.home_dir.mkdir(exist_ok=True)
        self.plugins_dir.mkdir(exist_ok=True)
    
    def get(self, key, default=None):
        return getattr(self, key, default)
    
    def set(self, key, value):
        setattr(self, key, value)
