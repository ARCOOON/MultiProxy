"""
firewall
========

Enterprise‑grade firewall plugin for the proxy.  This plugin applies a
list of rules to each incoming request and either permits or denies
traffic based on matching criteria.  A rule consists of an ``action``
(``allow`` or ``deny``) and a set of conditions, such as client IP
address, HTTP method, host or URL path.  Rules are evaluated in order,
and the first matching rule decides the fate of the request.  If no
rules match, the request is allowed by default.

The firewall does not persist rules on its own.  Use the
``FirewallConfig`` plugin to load and save rule sets to YAML.
"""
from __future__ import annotations

import ipaddress
from typing import Any, Dict, List, Optional

from ..plugin_base import BasePlugin, HTTPRequest


class Firewall(BasePlugin):
    name = "Firewall"
    version = "1.0.0"
    description = "Enterprise firewall with configurable rules"

    def __init__(self, manager) -> None:
        super().__init__(manager)
        # List of firewall rules.  Each rule is a dict with an 'action'
        # key ("allow" or "deny") and optional match criteria: 'ip',
        # 'method', 'host', 'path'.
        self.rules: List[Dict[str, Any]] = []

    def initialize(self) -> None:
        super().initialize()
        # Default rule set is empty (permit all)

    # Public API for other plugins
    def get_rules(self) -> List[Dict[str, Any]]:
        return list(self.rules)

    def set_rules(self, rules: List[Dict[str, Any]]) -> None:
        self.rules = list(rules)

    def add_rule(self, rule: Dict[str, Any], index: Optional[int] = None) -> None:
        if index is None:
            self.rules.append(rule)
        else:
            self.rules.insert(index, rule)

    def remove_rule(self, index: int) -> None:
        if 0 <= index < len(self.rules):
            self.rules.pop(index)

    def clear_rules(self) -> None:
        self.rules.clear()

    # Match helper
    def _match_rule(self, rule: Dict[str, Any], request: HTTPRequest) -> bool:
        # IP match: rule['ip'] may be an address or network in CIDR
        ip_condition = rule.get("ip")
        if ip_condition:
            try:
                network = ipaddress.ip_network(ip_condition, strict=False)
                # request.client is (host, port)
                client_ip = ipaddress.ip_address(request.client[0])
                if client_ip not in network:
                    return False
            except ValueError:
                return False
        # Method match
        method = rule.get("method")
        if method and request.method.upper() != method.upper():
            return False
        # Host match
        host = rule.get("host")
        if host and request.header("host"):
            if request.header("host").split(":")[0].lower() != host.lower():
                return False
        elif host:
            return False
        # Path match
        path = rule.get("path")
        if path and not request.path.startswith(path):
            return False
        return True

    def handle_request(self, request: HTTPRequest) -> bool:
        # Iterate through rules in order
        for rule in self.rules:
            if self._match_rule(rule, request):
                action = rule.get("action", "allow").lower()
                return action == "allow"
        # Default permit
        return True

    def get_commands(self):
        # The firewall itself does not expose CLI commands directly; the
        # shell plugin handles command parsing.  However, we register
        # an informational command to list rules.
        return {
            "show-firewall-rules": self._cmd_show_rules,
        }

    def _cmd_show_rules(self, args: List[str]) -> str:
        lines = []
        if not self.rules:
            return "No firewall rules configured."
        for idx, rule in enumerate(self.rules):
            parts = [f"{k}={v}" for k, v in rule.items()]
            lines.append(f"{idx}: " + ", ".join(parts))
        return "\n".join(lines)


# The Plugin class is what the plugin manager instantiates.
class Plugin(Firewall):
    pass