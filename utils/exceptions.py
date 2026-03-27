"""Custom exceptions"""


class StructoolError(Exception):
    """Base exception for structool"""
    pass


class FileError(StructoolError):
    """File operation error"""
    pass


class ParseError(StructoolError):
    """Parsing error"""
    pass


class ValidationError(StructoolError):
    """Validation error"""
    pass


class SelectionError(StructoolError):
    """Atom selection error"""
    pass


class GeometryError(StructoolError):
    """Geometry calculation error"""
    pass


class ConstraintError(StructoolError):
    """Constraint error"""
    pass


class VTSTError(StructoolError):
    """VTST tools error"""
    pass


class ConfigurationError(StructoolError):
    """Configuration error"""
    pass
