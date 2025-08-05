"""
shell
=====

Entry point for the interactive firewall shell.  This script creates
a `PluginManager`, loads the built‑in plugins (including the
`FirewallShell`), and then invokes the shell's REPL.  Run this module
to configure the firewall using a familiar Cisco‑style syntax.

Usage:

```bash
python -m proxy.shell
```

You can optionally specify an external plugins directory via the
`--plugins` option.  See `proxy/server.py` for details on plugin
loading.
"""
from __future__ import annotations

import argparse
from typing import Optional

from .plugin_manager import PluginManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Firewall shell")
    parser.add_argument("--plugins", type=str, help="Optional path to directory containing external plugins")
    args = parser.parse_args()
    manager = PluginManager()
    manager.load_builtin_plugins()
    if args.plugins:
        manager.load_external_plugins(args.plugins)
    # Find the FirewallShell plugin
    shell_plugin = None
    for plugin in manager.plugins:
        if plugin.name == "FirewallShell":
            shell_plugin = plugin
            break
    if shell_plugin is None:
        raise RuntimeError("FirewallShell plugin is not loaded")
    # Launch interactive shell
    shell_plugin.start_shell()
    # Finalize plugins when the shell exits
    manager.finalize_plugins()


if __name__ == "__main__":
    main()