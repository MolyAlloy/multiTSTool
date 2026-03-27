"""Geometry calculations"""
import numpy as np
from typing import Tuple, List


class Geometry:
    @staticmethod
    def distance(p1: np.ndarray, p2: np.ndarray) -> float:
        """Calculate distance between two points"""
        return np.linalg.norm(p2 - p1)
    
    @staticmethod
    def angle(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> float:
        """Calculate angle at p2"""
        v1 = p1 - p2
        v2 = p3 - p2
        cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))
        return np.arccos(np.clip(cos_angle, -1, 1)) * 180 / np.pi
    
    @staticmethod
    def dihedral(p1: np.ndarray, p2: np.ndarray, 
                 p3: np.ndarray, p4: np.ndarray) -> float:
        """Calculate dihedral angle"""
        b1 = p2 - p1
        b2 = p3 - p2
        b3 = p4 - p3
        
        n1 = np.cross(b1, b2)
        n2 = np.cross(b2, b3)
        
        n1 /= np.linalg.norm(n1)
        n2 /= np.linalg.norm(n2)
        
        m1 = np.cross(n1, b2 / np.linalg.norm(b2))
        
        x = np.dot(n1, n2)
        y = np.dot(m1, n2)
        
        return np.arctan2(y, x) * 180 / np.pi
    
    @staticmethod
    def center_of_mass(positions: np.ndarray, masses: List[float]) -> np.ndarray:
        """Calculate center of mass"""
        return np.average(positions, axis=0, weights=masses)
    
    @staticmethod
    def bond_matrix(positions: np.ndarray, cutoff: float = 3.0) -> np.ndarray:
        """Calculate bond connectivity matrix"""
        n = len(positions)
        bonds = np.zeros((n, n))
        
        for i in range(n):
            for j in range(i + 1, n):
                d = Geometry.distance(positions[i], positions[j])
                if d < cutoff:
                    bonds[i, j] = bonds[j, i] = 1
        
        return bonds
    
    @staticmethod
    def nearest_neighbors(positions: np.ndarray, n_neighbors: int = 12) -> List[List[int]]:
        """Find nearest neighbors for each atom"""
        from scipy.spatial import KDTree
        tree = KDTree(positions)
        return tree.query(positions, k=n_neighbors + 1)[1][:, 1:]
