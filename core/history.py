"""History management for undo/redo"""
from typing import Any, List, Optional
from datetime import datetime


class HistoryEntry:
    def __init__(self, action: str, data: Any):
        self.action = action
        self.data = data
        self.timestamp = datetime.now()


class History:
    def __init__(self, max_size: int = 100):
        self.entries: List[HistoryEntry] = []
        self.current_index: int = -1
        self.max_size = max_size
    
    def push(self, action: str, data: Any):
        """Add new entry"""
        if self.current_index < len(self.entries) - 1:
            self.entries = self.entries[:self.current_index + 1]
        
        self.entries.append(HistoryEntry(action, data))
        self.current_index += 1
        
        if len(self.entries) > self.max_size:
            self.entries.pop(0)
            self.current_index -= 1
    
    def undo(self) -> Optional[Any]:
        """Undo last action"""
        if self.current_index >= 0:
            entry = self.entries[self.current_index]
            self.current_index -= 1
            return entry.data
        return None
    
    def redo(self) -> Optional[Any]:
        """Redo last undone action"""
        if self.current_index < len(self.entries) - 1:
            self.current_index += 1
            return self.entries[self.current_index].data
        return None
    
    def can_undo(self) -> bool:
        """Check if undo is available"""
        return self.current_index >= 0
    
    def can_redo(self) -> bool:
        """Check if redo is available"""
        return self.current_index < len(self.entries) - 1
    
    def clear(self):
        """Clear history"""
        self.entries.clear()
        self.current_index = -1
