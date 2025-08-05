"""
plugin_manager
==============

Defines the `PluginManager` class responsible for loading and managing
plugins.  It coordinates the registration of built‑in and external
plugins, dispatches request/response events to each plugin and routes
CLI commands to the appropriate handler.

The manager expects each plugin module to expose a class called
`Plugin` that derives from `BasePlugin`.  During registration the
manager instantiates the class, calls its `initialize` method and
collects any CLI commands defined by the plugin.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .plugin_base import BasePlugin, HTTPRequest


class PluginManager:
    """Coordinates loading and execution of proxy plugins."""

    def __init__(self) -> None:
        self.plugins: List[BasePlugin] = []
        self.command_registry: Dict[str, Callable[[List[str]], Optional[str]]] = {}

    def load_builtin_plugins(self) -> None:
        """Load the built‑in plugins shipped with the proxy.

        Built‑ins live in ``proxy.plugins`` and must provide a class
        called ``Plugin`` derived from ``BasePlugin``.
        """
        import importlib
        import pkgutil

        package = "proxy.plugins"
        package_obj = __import__(package, fromlist=['*'])
        for _, module_name, _ in pkgutil.iter_modules(package_obj.__path__, package + "."):
            module = importlib.import_module(module_name)
            if hasattr(module, "Plugin"):
                cls = getattr(module, "Plugin")
                if not issubclass(cls, BasePlugin):
                    continue
                instance = cls(self)
                self.register_plugin(instance)

    def load_external_plugins(self, path: str) -> None:
        """Load plugins from an external directory.

        The directory must contain Python modules which expose a
        ``Plugin`` class derived from ``BasePlugin``.  Any import
        errors are logged and skipped.
        """
        import importlib.util
        import pathlib

        plugin_dir = pathlib.Path(path)
        if not plugin_dir.exists():
            return
        for file in plugin_dir.glob("*.py"):
            spec = importlib.util.spec_from_file_location(file.stem, file)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                    if hasattr(module, "Plugin"):
                        cls = getattr(module, "Plugin")
                        if issubclass(cls, BasePlugin):
                            instance = cls(self)
                            self.register_plugin(instance)
                except Exception as exc:
                    print(f"Failed to load plugin {file.name}: {exc}")

    def register_plugin(self, plugin: BasePlugin) -> None:
        """Register a plugin instance and initialise it.

        Also merges the plugin's CLI commands into the global
        command registry.
        """
        # Avoid duplicate names
        names = {p.name for p in self.plugins}
        if plugin.name in names:
            raise ValueError(f"Duplicate plugin name: {plugin.name}")
        self.plugins.append(plugin)
        plugin.initialize()
        # Register CLI commands
        for command, func in plugin.get_commands().items():
            if command in self.command_registry:
                raise ValueError(f"Duplicate command {command} registered by {plugin.name}")
            self.command_registry[command] = func

    def finalize_plugins(self) -> None:
        """Invoke the finalization hook on all plugins in reverse order."""
        for plugin in reversed(self.plugins):
            plugin.finalize()

    def process_request(self, request: HTTPRequest) -> bool:
        """Pass a request through each plugin's request hook.

        Returns ``True`` if all plugins allow the request or ``False``
        if any plugin denies it.  The chain stops at the first
        denial.
        """
        for plugin in self.plugins:
            try:
                ok = plugin.handle_request(request)
            except Exception as exc:
                print(f"Plugin {plugin.name} raised exception: {exc}")
                ok = False
            if not ok:
                return False
        return True

    def process_response(self, response: bytes, request: HTTPRequest) -> bytes:
        """Pass a response through each plugin's response hook.

        The plugins are invoked in the same order as for requests.  The
        output from one plugin becomes the input to the next.  Any
        exception raised by a plugin aborts processing and returns the
        most recent response.
        """
        data = response
        for plugin in self.plugins:
            try:
                data = plugin.handle_response(data, request)
            except Exception as exc:
                print(f"Plugin {plugin.name} raised exception during response: {exc}")
        return data

    def dispatch_command(self, line: str) -> Optional[str]:
        """Dispatch a CLI command to the appropriate plugin.

        Commands are matched by their first token.  Unknown commands
        return a helpful error message.
        """
        if not line.strip():
            return None
        tokens = line.strip().split()
        cmd = tokens[0]
        args = tokens[1:]
        func = self.command_registry.get(cmd)
        if func is None:
            return f"Unknown command: {cmd}"
        return func(args)