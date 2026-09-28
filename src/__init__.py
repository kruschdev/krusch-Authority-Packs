"""
krusch-authority-packs: Controlled Domain Scoping & Authority Pack Specification.
"""

from .validator import RagPack, RagPackValidator, ValidationError

__version__ = "1.0.0"
__all__ = ["RagPack", "RagPackValidator", "ValidationError"]
