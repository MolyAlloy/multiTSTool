"""Input validation utilities"""
import numpy as np
from typing import List, Any, Optional


class Validator:
    @staticmethod
    def validate_file_path(path: str) -> bool:
        """Validate file path"""
        if not path:
            raise ValueError("File path cannot be empty")
        return True
    
    @staticmethod
    def validate_positions(positions: np.ndarray) -> bool:
        """Validate atomic positions"""
        if positions is None or len(positions) == 0:
            raise ValueError("Positions cannot be empty")
        
        if not isinstance(positions, np.ndarray):
            raise TypeError("Positions must be numpy array")
        
        if len(positions.shape) != 2 or positions.shape[1] != 3:
            raise ValueError("Positions must have shape (N, 3)")
        
        if np.any(np.isnan(positions)) or np.any(np.isinf(positions)):
            raise ValueError("Positions contain NaN or Inf values")
        
        return True
    
    @staticmethod
    def validate_symbols(symbols: List[str]) -> bool:
        """Validate atomic symbols"""
        if not symbols:
            raise ValueError("Symbols list cannot be empty")
        
        valid_elements = {
            'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
            'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
            'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
            'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
            'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
            'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pt', 'Au',
            'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn'
        }
        
        for sym in symbols:
            if sym not in valid_elements:
                raise ValueError(f"Unknown element symbol: {sym}")
        
        return True
    
    @staticmethod
    def validate_cell(cell: Optional[np.ndarray]) -> bool:
        """Validate unit cell"""
        if cell is None:
            return True
        
        if not isinstance(cell, np.ndarray):
            raise TypeError("Cell must be numpy array")
        
        if cell.shape != (3, 3):
            raise ValueError("Cell must have shape (3, 3)")
        
        if np.linalg.det(cell) <= 0:
            raise ValueError("Cell volume must be positive")
        
        return True
    
    @staticmethod
    def validate_atom_index(index: int, n_atoms: int) -> bool:
        """Validate atom index"""
        if index < 0 or index >= n_atoms:
            raise ValueError(f"Atom index {index} out of range [0, {n_atoms})")
        return True
    
    @staticmethod
    def validate_distance(distance: float) -> bool:
        """Validate distance value"""
        if distance < 0:
            raise ValueError("Distance cannot be negative")
        if np.isnan(distance) or np.isinf(distance):
            raise ValueError("Distance must be finite")
        return True
