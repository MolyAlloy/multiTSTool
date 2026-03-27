"""Atom selection utilities"""
from typing import List, Set, Callable
import numpy as np


class Selection:
    def __init__(self):
        self.selected_indices: Set[int] = set()
    
    def select(self, indices: List[int]):
        """Select atoms by indices"""
        self.selected_indices = set(indices)
    
    def add(self, indices: List[int]):
        """Add to selection"""
        self.selected_indices.update(indices)
    
    def remove(self, indices: List[int]):
        """Remove from selection"""
        self.selected_indices.difference_update(indices)
    
    def clear(self):
        """Clear selection"""
        self.selected_indices.clear()
    
    def get_indices(self) -> List[int]:
        """Get selected indices"""
        return sorted(self.selected_indices)
    
    def invert(self, total_atoms: int):
        """Invert selection"""
        all_indices = set(range(total_atoms))
        self.selected_indices = all_indices - self.selected_indices
    
    def filter_by_element(self, symbols: List[str], element: str) -> List[int]:
        """Select atoms by element"""
        return [i for i, sym in enumerate(symbols) if sym == element]
    
    def filter_by_position(self, symbols: List[str], positions: np.ndarray,
                          predicate: Callable[[np.ndarray], bool]) -> List[int]:
        """Select atoms by position predicate"""
        return [i for i, pos in enumerate(positions) if predicate(pos)]
    
    def filter_by_distance(self, symbols: List[str], positions: np.ndarray,
                          ref_pos: np.ndarray, max_dist: float) -> List[int]:
        """Select atoms within distance of reference position"""
        distances = np.linalg.norm(positions - ref_pos, axis=1)
        return [i for i, d in enumerate(distances) if d <= max_dist]
