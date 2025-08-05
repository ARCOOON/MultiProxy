"""Built‑in plugins for the proxy server.

This package contains three modules:

* `firewall` – Enterprise firewall plugin.
* `firewall_config` – YAML persistence for firewall rules.
* `firewall_shell` – Interactive CLI for managing the firewall.

Plugins are automatically discovered by the `PluginManager` and
registered at startup.  Each module must expose a class named
`Plugin` deriving from `BasePlugin`.
"""

__all__ = ["firewall", "firewall_config", "firewall_shell"]