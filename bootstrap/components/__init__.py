"""Component subpackage."""

from .base import Component, ComponentFailure
from .registry import register, CATALOG, build_registry, resolve_closure
from . import catalog  # noqa: F401  (registers entries)

__all__ = [
    "Component",
    "ComponentFailure",
    "register",
    "CATALOG",
    "build_registry",
    "resolve_closure",
]