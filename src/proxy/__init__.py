"""Top‑level package for the Python proxy server.

Exposes common classes so that they can be imported directly from
`proxy`, e.g. `from proxy.server import ProxyServer`.
"""

from .server import ProxyServer
from .plugin_manager import PluginManager
from .plugin_base import BasePlugin, HTTPRequest

__all__ = ["ProxyServer", "PluginManager", "BasePlugin", "HTTPRequest"]