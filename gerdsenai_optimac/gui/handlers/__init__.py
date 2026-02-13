"""
Handler modules for OptiMac menu bar actions.

Each module provides a ``build_menu(app)`` function that returns
a ``rumps.MenuItem`` submenu with all callbacks wired up.
"""

from gerdsenai_optimac.gui.handlers import (  # noqa: F401
    ai_stack,
    system,
    performance,
    network,
    security,
    optimize,
)
