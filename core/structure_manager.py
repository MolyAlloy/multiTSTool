"""Structure manager for manipulating atomic structures"""
import numpy as np
from typing import List, Optional, Tuple


class StructureManager:
    def __init__(self):
        self.structure = None
    
    def set_structure(self, data: dict):
        """Set structure data"""
        self.structure = {
            'symbols': data.get('symbols', []),
            'positions': np.array(data.get('positions', [])),
            'cell': data.get('cell'),
            'constraints': data.get('constraints', [])
        }
    
    def get_positions(self) -> np.ndarray:
        """Get atomic positions"""
        return self.structure['positions'] if self.structure else None
    
    def set_positions(self, positions: np.ndarray):
        """Set atomic positions"""
        if self.structure is not None:
            self.structure['positions'] = positions
    
    def get_symbols(self) -> List[str]:
        """Get atomic symbols"""
        return self.structure['symbols'] if self.structure else []
    
    def get_cell(self) -> Optional[np.ndarray]:
        """Get unit cell"""
        return self.structure.get('cell') if self.structure else None
    
    def translate(self, displacement: np.ndarray):
        """Translate all atoms"""
        if self.structure is not None:
            self.structure['positions'] += displacement
    
    def wrap_atoms(self):
        """Wrap atoms into unit cell"""
        if self.structure is None or self.structure['cell'] is None:
            return
        
        cell = self.structure['cell']
        inv_cell = np.linalg.inv(cell)
        positions = self.structure['positions']
        
        fractional = positions @ inv_cell
        fractional = fractional - np.floor(fractional)
        self.structure['positions'] = fractional @ cell
    
    def get_distance(self, i: int, j: int) -> float:
        """Calculate distance between two atoms"""
        pos = self.structure['positions']
        return np.linalg.norm(pos[i] - pos[j])
    
    def get_angle(self, i: int, j: int, k: int) -> float:
        """Calculate angle between three atoms"""
        pos = self.structure['positions']
        v1 = pos[i] - pos[j]
        v2 = pos[k] - pos[j]
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return np.arccos(np.clip(cos_angle, -1, 1)) * 180 / np.pi
