from __future__ import annotations

import importlib
import pkgutil

from app.capabilities.tools.interfaces import ToolPlugin


def load_builtin_tool_plugins() -> list[ToolPlugin]:
    """Discover TOOL_PLUGIN exports from app.capabilities.tools.plugins."""
    import app.capabilities.tools.plugins as plugins_pkg

    out: list[ToolPlugin] = []
    for modinfo in pkgutil.iter_modules(plugins_pkg.__path__):
        if modinfo.name.startswith("_"):
            continue
        module = importlib.import_module(f"{plugins_pkg.__name__}.{modinfo.name}")
        plugin = getattr(module, "TOOL_PLUGIN", None)
        if isinstance(plugin, ToolPlugin):
            out.append(plugin)
    out.sort(key=lambda p: p.name)
    return out
