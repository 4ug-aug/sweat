from responsibilities.base import BaseResponsibility, ResponsibilityItem

__all__ = [
    "BaseResponsibility",
    "ResponsibilityItem",
    "RESPONSIBILITY_TYPES",
]


def __getattr__(name: str):
    if name == "RESPONSIBILITY_TYPES":
        from responsibilities.registry import RESPONSIBILITY_TYPES
        return RESPONSIBILITY_TYPES
    raise AttributeError(f"module 'responsibilities' has no attribute {name!r}")
