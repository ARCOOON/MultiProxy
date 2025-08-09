# dynamic_pac_server.py
import ipaddress
import http.server
import socketserver
from typing import List, Dict, Tuple

# Define your routing rules here
CONFIG: Dict[str, List] = {
    # Domains to bypass (direct connection)
    "direct_domains": [".local", ".rtx-asus", ".rtx-asus.local"],
    # Subnets to bypass (CIDR notation)
    "direct_subnets": ["192.168.50.0/24"],
    # Protocol-specific proxies: protocol -> proxy string
    "protocol_proxies": {
        "http:": "PROXY 192.168.50.115:8443",
        "https:": "PROXY 192.168.50.115:8443",
        # ftp: etc.
    },
    # Default proxy and failover (semicolon-separated)
    "default_proxy": "PROXY  192.168.50.115:8443; DIRECT",
}

def generate_pac(config: Dict[str, List]) -> str:
    direct_domains = config["direct_domains"]
    direct_subnets = [ipaddress.ip_network(net) for net in config["direct_subnets"]]
    protocol_proxies = config["protocol_proxies"]
    default_proxy = config["default_proxy"]

    # JavaScript helpers for subnet checks
    subnet_checks = []
    for net in direct_subnets:
        subnet_checks.append(
            f'isInNet(host, "{net.network_address}", "{net.netmask}")'
        )
    subnet_expr = " || ".join(subnet_checks)

    # Domains check
    domain_checks = []
    for dom in direct_domains:
        if dom.startswith("."):
            domain_checks.append(f'dnsDomainIs(host, "{dom}")')
        else:
            domain_checks.append(f'host == "{dom}"')
    domain_checks.append("isPlainHostName(host)")
    domain_expr = " || ".join(domain_checks)

    # Protocol-based proxy logic
    protocol_lines = []
    for proto, proxy_str in protocol_proxies.items():
        prefix = proto if proto.endswith(":") else f"{proto}:"
        protocol_lines.append(
            f'  if (url.substring(0, {len(prefix)}) == "{prefix}") return "{proxy_str}";'
        )
    protocol_logic = "\n".join(protocol_lines)

    # Build the PAC function
    pac = f"""\
    function FindProxyForURL(url, host) {{
      // Bypass plain hostnames and specified domains
      if ({domain_expr}) return "DIRECT";
      // Bypass specified subnets
      if ({subnet_expr}) return "DIRECT";
    {protocol_logic}
      // Default proxy with failover
      return "{default_proxy}";
    }}
    """
    return pac

PAC_CONTENT = generate_pac(CONFIG)

class PACHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/proxy.pac", "/wpad.dat"):
            content = PAC_CONTENT.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ns-proxy-autoconfig")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            self.send_error(404, "Not Found")

    def log_message(self, *args):
        pass

def main():
    with socketserver.ThreadingTCPServer(("0.0.0.0", 8000), PACHandler) as httpd:
        print("Serving dynamic PAC file at http://<server-ip>:8000/proxy.pac")
        httpd.serve_forever()

if __name__ == "__main__":
    main()
