""" di

Dependency injection module.
"""

from app.kernel.di.container import Container, get_container, reset_container

__all__ = ["Container", "get_container", "reset_container"]

