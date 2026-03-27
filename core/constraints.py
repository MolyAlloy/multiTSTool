"""Constraints management"""
import numpy as np
from typing import List, Tuple, Optional


class Constraints:
    def __init__(self):
        self.fixed_indices: List[int] = []
        self.fixed_axes: List[Tuple[int, int]] = []
        self.distance_constraints: List[Tuple[int, int, float]] = []
        self.angle_constraints: List[Tuple[int, int, int, float]] = []
    
    def add_fixed(self, indices: List[int]):
        """Fix atom positions"""
        self.fixed_indices.extend(indices)
    
    def remove_fixed(self, indices: List[int]):
        """Unfix atom positions"""
        self.fixed_indices = [i for i in self.fixed_indices if i not in indices]
    
    def add_distance(self, i: int, j: int, target: float):
        """Add distance constraint"""
        self.distance_constraints.append((i, j, target))
    
    def add_angle(self, i: int, j: int, k: int, target: float):
        """Add angle constraint"""
        self.angle_constraints.append((i, j, k, target))
    
    def clear(self):
        """Clear all constraints"""
        self.fixed_indices.clear()
        self.fixed_axes.clear()
        self.distance_constraints.clear()
        self.angle_constraints.clear()
    
    def is_fixed(self, index: int) -> bool:
        """Check if atom is fixed"""
        return index in self.fixed_indices
    
    def apply(self, positions: np.ndarray) -> np.ndarray:
        """Apply constraints to positions"""
        return positions.copy()
