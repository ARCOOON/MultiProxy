"""
firewall_config
===============

Plugin that persists the firewall rules to and from a YAML
configuration file.  It sits on top of the `Firewall` plugin and
serialises its rule list.  Rules are stored under a top‑level `rules`
key in the YAML document.  You can point the plugin at a custom
filename (default is `config.yaml` in the proxy package) when
instantiating the proxy server.

CLI commands provided by this plugin:

* ``load-config [filename]`` — load firewall rules from a YAML file.
  If no filename is provided, the plugin uses its configured default.
* ``save-config [filename]`` — write current rules to a YAML file.
* ``reset-config`` — clear all rules in the firewall.

This plugin relies on the presence of the `Firewall` plugin.  It will
raise an exception if no firewall is loaded.
"""
from __future__ import annotations

import os
from typing import List, Optional

import yaml

from ..plugin_base import BasePlugin, HTTPRequest


class FirewallConfig(BasePlugin):
    name = "FirewallConfig"
    version = "1.0.0"
    description = "Persist firewall rules to YAML and restore them on startup"

    def __init__(self, manager, filename: Optional[str] = None) -> None:
        super().__init__(manager)
        # Default configuration file relative to this package
        self.filename = filename or os.path.join(os.path.dirname(__file__), "..", "config.yaml")
        self.firewall = None

    def initialize(self) -> None:
        super().initialize()
        # Locate the firewall plugin
        for plugin in self.manager.plugins:
            if plugin.name == "Firewall":
                self.firewall = plugin
                break
        if self.firewall is None:
            raise RuntimeError("FirewallConfig requires the Firewall plugin to be loaded")
        # Attempt to load initial configuration
        try:
            self.load_config(self.filename)
        except FileNotFoundError:
            # No config present; leave rules empty
            pass

    # CLI commands
    def get_commands(self):
        return {
            "load-config": self._cmd_load,
            "save-config": self._cmd_save,
            "reset-config": self._cmd_reset,
        }

    def _cmd_load(self, args: List[str]) -> str:
        filename = args[0] if args else self.filename
        try:
            self.load_config(filename)
            return f"Loaded firewall rules from {filename}"
        except Exception as exc:
            return f"Failed to load config: {exc}"

    def _cmd_save(self, args: List[str]) -> str:
        filename = args[0] if args else self.filename
        try:
            self.save_config(filename)
            return f"Saved firewall rules to {filename}"
        except Exception as exc:
            return f"Failed to save config: {exc}"

    def _cmd_reset(self, args: List[str]) -> str:
        if self.firewall:
            self.firewall.clear_rules()
            return "Cleared firewall rules"
        return "Firewall plugin not found"

    # Persistence methods
    def load_config(self, filename: str) -> None:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        rules = data.get("rules", [])
        if self.firewall:
            self.firewall.set_rules(rules)

    def save_config(self, filename: str) -> None:
        if self.firewall:
            rules = self.firewall.get_rules()
        else:
            rules = []
        with open(filename, "w", encoding="utf-8") as f:
            yaml.safe_dump({"rules": rules}, f, sort_keys=False)

    # The config plugin does not participate in request/response handling
    # and therefore leaves these hooks as no‑ops.
    def handle_request(self, request: HTTPRequest) -> bool:
        return True

    def handle_response(self, response: bytes, request: HTTPRequest) -> bytes:
        return response


class Plugin(FirewallConfig):
    pass