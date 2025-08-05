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
        """
        Return True if the request matches all of the conditions in the rule.

        Supported rule keys (aliases in parentheses):
          - action: "allow" or "deny" (checked in handle_request)
          - src_ip (src, source, ip): source IP or CIDR range
          - dst_ip (dst, dest, destination): destination IP or CIDR range
          - src_port (sport, source_port): source port number
          - dst_port (port, dest_port): destination port number
          - domain (host): destination host or suffix (e.g. "example.com")
          - protocol: "http", "tcp", "websocket", etc.
          - method: HTTP method (e.g. "GET")
          - path: URL path prefix
        Unknown keys are ignored.
        """
        # Resolve client IP and port
        try:
            client_ip = ipaddress.ip_address(request.client[0])
            client_port = request.client[1]
        except Exception:
            return False

        # Resolve destination host and port from Host header
        host_header = request.header("host")
        dest_host: Optional[str] = None
        dest_port: int = 80

        if host_header:
            dest_host = host_header.split(":")[0]
            if ":" in host_header:
                try:
                    dest_port = int(host_header.rsplit(":", 1)[1])
                except ValueError:
                    dest_port = 80

        # Determine protocol: CONNECT implies raw TCP; otherwise HTTP
        req_protocol = "tcp" if request.method.upper() == "CONNECT" else "http"

        # --- Source IP ---
        src_ip = (
            rule.get("src_ip")
            or rule.get("src")
            or rule.get("source")
            or rule.get("ip")
        )

        if src_ip:
            try:
                network = ipaddress.ip_network(src_ip, strict=False)
                if client_ip not in network:
                    return False
            except ValueError:
                return False

        # --- Destination IP ---
        dst_ip = (
            rule.get("dst_ip")
            or rule.get("dst")
            or rule.get("dest")
            or rule.get("destination")
        )

        if dst_ip:
            if not dest_host:
                return False
            try:
                dest_ip_obj = ipaddress.ip_address(dest_host)
                dest_network = ipaddress.ip_network(dst_ip, strict=False)
                if dest_ip_obj not in dest_network:
                    return False
            except ValueError:
                return False

        # --- Domain/host match ---
        domain = rule.get("domain") or rule.get("host")
        if domain:
            if not dest_host:
                return False

            d = domain.lower()
            h = dest_host.lower()

            # allow suffix match (e.g. "example.com" matches "sub.example.com")
            if h != d and not h.endswith("." + d):
                return False

        # --- Source port ---
        src_port = rule.get("src_port") or rule.get("sport") or rule.get("source_port")
        if src_port:
            try:
                if client_port != int(src_port):
                    return False
            except ValueError:
                return False

        # --- Destination port ---
        dst_port = rule.get("dst_port") or rule.get("port") or rule.get("dest_port")
        if dst_port:
            try:
                if dest_port != int(dst_port):
                    return False
            except ValueError:
                return False

        # --- Protocol ---
        protocol = rule.get("protocol")
        if protocol and req_protocol != protocol.lower():
            return False

        # --- HTTP method ---
        method = rule.get("method")
        if method and request.method.upper() != method.upper():
            return False

        # --- URL path ---
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
