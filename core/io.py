"""I/O operations for structure files"""
from pathlib import Path
from typing import Optional
import numpy as np


class StructureIO:
    SUPPORTED_FORMATS = ['xyz', 'vasp', 'cif', 'pdb']
    
    @staticmethod
    def read(filepath: str):
        """Read structure from file"""
        path = Path(filepath)
        ext = path.suffix[1:]
        
        if ext == 'xyz':
            return StructureIO._read_xyz(path)
        elif ext == 'vasp':
            return StructureIO._read_vasp(path)
        elif ext == 'cif':
            return StructureIO._read_cif(path)
        else:
            raise ValueError(f"Unsupported format: {ext}")
    
    @staticmethod
    def write(filepath: str, structure):
        """Write structure to file"""
        path = Path(filepath)
        ext = path.suffix[1:]
        
        if ext == 'xyz':
            StructureIO._write_xyz(path, structure)
        elif ext == 'vasp':
            StructureIO._write_vasp(path, structure)
        else:
            raise ValueError(f"Unsupported format: {ext}")
    
    @staticmethod
    def _read_xyz(path):
        """Read XYZ file"""
        positions = []
        symbols = []
        with open(path) as f:
            lines = f.readlines()
            n_atoms = int(lines[0].strip())
            for line in lines[2:2+n_atoms]:
                parts = line.split()
                symbols.append(parts[0])
                positions.append([float(x) for x in parts[1:]])
        
        return {
            'symbols': symbols,
            'positions': np.array(positions),
            'cell': None
        }
    
    @staticmethod
    def _read_vasp(path):
        """Read POSCAR file"""
        pass
    
    @staticmethod
    def _read_cif(path):
        """Read CIF file"""
        pass
    
    @staticmethod
    def _write_xyz(path, structure):
        """Write XYZ file"""
        symbols = structure.get('symbols', [])
        positions = structure.get('positions', [])
        with open(path, 'w') as f:
            f.write(f"{len(symbols)}\n")
            f.write("Created by structool\n")
            for sym, pos in zip(symbols, positions):
                f.write(f"{sym} {pos[0]:.6f} {pos[1]:.6f} {pos[2]:.6f}\n")
    
    @staticmethod
    def _write_vasp(path, structure):
        """Write POSCAR file"""
        pass
