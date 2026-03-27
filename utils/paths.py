"""Path utilities"""
from pathlib import Path
from typing import List, Optional


class PathManager:
    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
    
    def resolve(self, path: str) -> Path:
        """Resolve path relative to base directory"""
        p = Path(path)
        if p.is_absolute():
            return p
        return (self.base_dir / p).resolve()
    
    def find_files(self, pattern: str) -> List[Path]:
        """Find files matching pattern"""
        return list(self.base_dir.glob(pattern))
    
    def ensure_dir(self, path: str) -> Path:
        """Ensure directory exists"""
        p = self.resolve(path)
        p.mkdir(parents=True, exist_ok=True)
        return p
    
    def get_relative_path(self, path: str) -> Path:
        """Get path relative to base directory"""
        p = Path(path)
        try:
            return p.relative_to(self.base_dir)
        except ValueError:
            return p
    
    def is_subpath(self, path: str) -> bool:
        """Check if path is under base directory"""
        p = self.resolve(path)
        try:
            p.relative_to(self.base_dir)
            return True
        except ValueError:
            return False
