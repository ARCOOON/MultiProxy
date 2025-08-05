"""
firewall_shell
==============

Interactive command shell plugin for the firewall.  This plugin
provides a Cisco‑style CLI that allows administrators to inspect and
manipulate firewall rules in a familiar syntax.  The shell exposes
commands similar to those found on networking gear:

```
show firewall rules               # display current rules
configure terminal                # enter configuration mode
 rule add deny ip=10.0.0.0/8      # add a rule (inside config mode)
 rule del 0                       # delete rule by index
 exit                             # exit config mode
write memory                      # save rules to YAML via FirewallConfig
```

This shell is separate from the proxy process; run it from
``python -m proxy.shell``.  It relies on the presence of the
`Firewall` and `FirewallConfig` plugins.  When the shell starts it
looks up these plugins via the manager passed to its constructor.
"""

from __future__ import annotations

import shlex
from typing import Callable, Dict, List

from ..plugin_base import BasePlugin, HTTPRequest


class FirewallShell(BasePlugin):
    name = "FirewallShell"
    version = "1.0.0"
    description = "Cisco‑style CLI for configuring the firewall"

    def __init__(self, manager) -> None:
        super().__init__(manager)
        self.firewall = None
        self.config = None
        self._running = False

    def initialize(self) -> None:
        super().initialize()
        # Locate dependencies
        for plugin in self.manager.plugins:
            if plugin.name == "Firewall":
                self.firewall = plugin
            if plugin.name == "FirewallConfig":
                self.config = plugin
        if self.firewall is None:
            raise RuntimeError("FirewallShell requires the Firewall plugin")

    def get_commands(self) -> dict[str, Callable[..., str]]:
        # Expose a 'shell' command that runs the interactive loop
        return {
            "shell": self._cmd_shell,
        }

    def _cmd_shell(self, args: List[str]) -> str:
        # Launch interactive shell
        self.start_shell()
        return ""

    # Shell implementation
    def start_shell(self) -> None:
        self._running = True

        print("Entering firewall shell.  Type 'help' for assistance.  Ctrl+C to exit.")
        mode = "exec"  # exec vs config

        while self._running:
            try:
                prompt = "(config)# " if mode == "config" else "# "
                line = input(prompt)
            except (EOFError, KeyboardInterrupt):
                print("\nExiting shell.")
                break

            if not line.strip():
                continue

            tokens = shlex.split(line)
            cmd = tokens[0].lower()
            args = tokens[1:]

            if mode == "exec":
                if cmd in ("help", "?"):
                    self._print_help()
                elif cmd in ("show",):
                    self._handle_show(args)
                elif cmd in ("configure", "conf"):
                    if args and args[0] in ("terminal", "t"):
                        mode = "config"
                        print("Entering configuration mode.  Type 'exit' to leave.")
                    else:
                        print("Usage: configure terminal")
                elif cmd in ("write", "wr"):
                    if args and args[0] in ("memory", "mem"):
                        self._handle_write()
                    else:
                        print("Usage: write memory")
                else:
                    print(f"Unknown command: {cmd}")
            elif mode == "config":
                if cmd == "exit":
                    mode = "exec"
                    print("Leaving configuration mode.")
                elif cmd == "rule":
                    self._handle_rule(args)
                elif cmd in ("show",):
                    self._handle_show(args)
                else:
                    print(f"Unknown config command: {cmd}")

    # Exec‑mode handlers
    def _print_help(self) -> None:
        print("Available commands:")
        print("  show rules                 - Display current firewall rules")
        print("  configure terminal         - Enter configuration mode")
        print("  write memory               - Save rules to config file")
        print("  help                       - Show this help message")
        print("\nConfiguration mode commands:")
        print("  rule add <allow|deny> [key=value ...]  - Add a rule")
        print("    Supported keys:")
        print(
            "      src_ip, dst_ip, src_port, dst_port, domain, protocol, method, path, description"
        )
        print(
            "      (aliases: src, source, ip, dst, dest, destination, sport, source_port, port, dest_port, host)"
        )
        print("  rule del <index>                        - Delete rule by index")
        print("  rule show <index>                       - Show a single rule")

    def _handle_show(self, args: List[str]) -> None:
        if args[:1] == ["rules"]:
            if self.firewall:
                rules = self.firewall.get_rules()
                if not rules:
                    print("No firewall rules configured.")
                else:
                    for idx, rule in enumerate(rules):
                        parts = [f"{k}={v}" for k, v in rule.items()]
                        print(f"{idx}: " + ", ".join(parts))
            else:
                print("Firewall plugin not loaded")
        else:
            print("Usage: show rules")

    def _handle_write(self) -> None:
        if self.config:
            self.config.save_config(self.config.filename)
            print(f"Firewall rules saved to {self.config.filename}")
        else:
            print("FirewallConfig plugin not loaded; cannot save")

    # Config‑mode handlers
    def _handle_rule(self, args: List[str]) -> None:
        if not args:
            print(
                "Usage: rule add <allow|deny> [key=value ...]\n"
                "       rule del <index>\n"
                "       rule show <index>"
            )
            return

        subcmd = args[0].lower()
        if subcmd == "add":
            if len(args) < 2:
                print(
                    "Usage: rule add <allow|deny> key=value ... "
                    "(see 'help' for supported keys)"
                )
                return

            action = args[1].lower()
            if action not in ("allow", "deny"):
                print("Action must be 'allow' or 'deny'")
                return

            params: Dict[str, str] = {"action": action}
            # Aliases for parameter names
            alias_map = {
                "src": "src_ip",
                "source": "src_ip",
                "ip": "src_ip",
                "src_ip": "src_ip",
                "dst": "dst_ip",
                "dest": "dst_ip",
                "destination": "dst_ip",
                "dst_ip": "dst_ip",
                "sport": "src_port",
                "source_port": "src_port",
                "src_port": "src_port",
                "port": "dst_port",
                "dest_port": "dst_port",
                "dst_port": "dst_port",
                "proto": "protocol",
                "protocol": "protocol",
                "host": "domain",
                "domain": "domain",
                "method": "method",
                "path": "path",
                "desc": "description",
                "description": "description",
            }

            for token in args[2:]:
                if "=" not in token:
                    print(f"Ignoring invalid token: {token}")
                    continue

                key, value = token.split("=", 1)
                norm_key = alias_map.get(key.lower())

                if not norm_key:
                    print(f"Unknown key: {key}")
                    continue

                # Remove surrounding quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                params[norm_key] = value

            if self.firewall:
                self.firewall.add_rule(params)
                print(f"Rule added: {params}")
            else:
                print("Firewall plugin not loaded")
        elif subcmd in ("del", "remove"):
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: rule del <index>")
                return

            idx = int(args[1])

            if self.firewall:
                rules = self.firewall.get_rules()
                if 0 <= idx < len(rules):
                    self.firewall.remove_rule(idx)
                    print(f"Removed rule {idx}.")
                else:
                    print("Index out of range")
            else:
                print("Firewall plugin not loaded")
        elif subcmd == "show":
            if len(args) < 2 or not args[1].isdigit():
                print("Usage: rule show <index>")
                return

            idx = int(args[1])

            if self.firewall:
                rules = self.firewall.get_rules()
                if 0 <= idx < len(rules):
                    rule = rules[idx]
                    print(f"{idx}: " + ", ".join(f"{k}={v}" for k, v in rule.items()))
                else:
                    print("Index out of range")
            else:
                print("Firewall plugin not loaded")

        else:
            print(f"Unknown rule subcommand: {subcmd}")

    # The shell plugin does not handle HTTP events
    def handle_request(self, request: HTTPRequest) -> bool:
        return True

    def handle_response(self, response: bytes, request: HTTPRequest) -> bytes:
        return response


class Plugin(FirewallShell):
    pass
